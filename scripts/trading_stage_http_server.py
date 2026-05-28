"""HTTP runner for n8n -> trading Python stages.

Runs inside the trading-runner Docker service. n8n should call:

POST /run-stage
{"stage": "news_briefing_growth_analysis"}

The server executes scripts/run_daily_workflow_stage.py and returns parsed JSON.
It never accepts arbitrary shell commands.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(os.environ.get("TRADING_PROJECT_ROOT", "/app")).resolve()
ALLOWED_STAGES = {
    "system_health_check",
    "news_briefing_growth_analysis",
    "stock_morning_signals",
    "stock_trading_daily_workflow",
    "premarket_account_risk_check",
    "candidate_compression_layer",
    "morning_investment_layer",
    "opening_10m_aggressive_layer",
    "opening_30m_standard_layer",
    "post_opening_monitoring",
    "midday_position_review",
    "pre_close_risk_review",
    "evening_selloff_layer",
    "aftermarket_multi_timeframe_collection",
    "stock_nightly_collection",
    "daily_pnl_feedback_report",
    "ka10005_timeframe_validation",
    "collect_intraday_90d",
    "backtest_opening_strategy_90d",
    "simulate_approved_orders",
    "strategy_review_if_needed",
}


def read_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        env[key.strip()] = value
    return env


def telegram_config() -> tuple[str | None, str | None]:
    env = {}
    env.update(read_env_file(PROJECT_ROOT / ".env"))
    env.update(read_env_file(Path.home() / ".hermes" / ".env"))
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID") or env.get("HERMES_TELEGRAM_CHAT_ID")
    return token, chat_id


def summarize_for_telegram(data: dict[str, Any]) -> str:
    stage = data.get("stage") or data.get("workflow") or "unknown"
    status = data.get("status", "unknown")
    ok = data.get("ok")
    blocks = data.get("blocking_conditions") or []
    alerts = data.get("alerts") or []
    summary = data.get("summary") or {}
    lines = [
        f"[Trading n8n] {stage}",
        f"ok={ok} status={status}",
    ]
    if isinstance(summary, dict) and summary:
        small = {k: summary[k] for k in list(summary)[:6]}
        lines.append("summary=" + json.dumps(small, ensure_ascii=False))
    if alerts:
        lines.append("alerts=" + ", ".join(map(str, alerts[:5])))
    if blocks:
        lines.append("blocks=" + ", ".join(map(str, blocks[:5])))
    return "\n".join(lines)[:3500]


def send_telegram_message(text: str) -> dict[str, Any]:
    token, chat_id = telegram_config()
    if not token or not chat_id:
        return {"ok": False, "blocking_conditions": ["telegram_config_missing"]}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "blocking_conditions": ["telegram_send_failed"], "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": bool(payload.get("ok")), "message_id": payload.get("result", {}).get("message_id")}


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


class Handler(BaseHTTPRequestHandler):
    server_version = "TradingStageHTTP/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: N802
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            token, chat_id = telegram_config()
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "service": "trading-runner",
                    "project_root": str(PROJECT_ROOT),
                    "python": sys.version.split()[0],
                    "telegram_config_present": bool(token and chat_id),
                },
            )
            return
        json_response(self, 404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/run-stage":
            json_response(self, 404, {"ok": False, "error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(body or "{}")
        except Exception as exc:  # noqa: BLE001
            json_response(self, 400, {"ok": False, "error": "invalid_json", "message": str(exc)})
            return
        stage = str(payload.get("stage") or "")
        if stage not in ALLOWED_STAGES:
            json_response(self, 400, {"ok": False, "error": "stage_not_allowed", "stage": stage})
            return
        timeout = int(payload.get("timeout", 420))
        timeout = max(10, min(timeout, 900))
        cmd = [sys.executable, "scripts/run_daily_workflow_stage.py", "--stage", stage]
        try:
            proc = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            json_response(
                self,
                504,
                {
                    "ok": False,
                    "workflow": "daily_trading_workflow_v1",
                    "stage": stage,
                    "status": "blocked",
                    "blocking_conditions": ["stage_timeout"],
                },
            )
            return
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            data = {
                "ok": False,
                "workflow": "daily_trading_workflow_v1",
                "stage": stage,
                "status": "blocked",
                "blocking_conditions": ["stage_invalid_json"],
                "stdout_tail": proc.stdout[-2000:],
            }
        if proc.stderr:
            data.setdefault("stderr_tail", proc.stderr[-1200:])
        data.setdefault("runner_returncode", proc.returncode)
        if payload.get("notify", False):
            data["telegram_notification"] = send_telegram_message(summarize_for_telegram(data))
        # HTTP 200 means the runner worked. Trading blocks are represented in JSON.
        json_response(self, 200, data)


def main() -> int:
    host = os.environ.get("TRADING_RUNNER_HOST", "0.0.0.0")
    port = int(os.environ.get("TRADING_RUNNER_PORT", "8765"))
    if not (PROJECT_ROOT / "scripts" / "run_daily_workflow_stage.py").exists():
        print(f"missing run_daily_workflow_stage.py under {PROJECT_ROOT}", file=sys.stderr)
        return 2
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"trading-runner listening on {host}:{port} project_root={PROJECT_ROOT}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
