"""Check Telegram delivery readiness without exposing credentials.

If TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID exist, sends a small test message.
Otherwise returns blocking_conditions for n8n credential/manual setup.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import read_env  # noqa: E402


def read_telegram_env() -> dict[str, str]:
    """Read project .env, then Hermes .env as fallback; never print values."""
    env = read_env(PROJECT_ROOT / ".env")
    hermes_env = read_env(Path.home() / ".hermes" / ".env")
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "HERMES_TELEGRAM_CHAT_ID"):
        if not env.get(key) and hermes_env.get(key):
            env[key] = hermes_env[key]
    return env


def main() -> int:
    env = read_telegram_env()
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID") or env.get("HERMES_TELEGRAM_CHAT_ID")
    blocks: list[str] = []
    if not token:
        blocks.append("missing_telegram_bot_token")
    if not chat_id:
        blocks.append("missing_telegram_chat_id")
    if blocks:
        print(json.dumps({
            "ok": False,
            "workflow": "daily_trading_workflow_v1",
            "stage": "telegram_connection_check",
            "status": "blocked",
            "blocking_conditions": blocks,
            "next_actions": ["Set Telegram credential inside n8n or add TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID to .env locally."],
        }, ensure_ascii=False, indent=2))
        return 2

    text = f"[Hermes trading] Telegram 연결 테스트 OK - {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    data = urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data, method="POST")
    try:
        with urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            ok = bool(parsed.get("ok"))
            out = {"ok": ok, "workflow": "daily_trading_workflow_v1", "stage": "telegram_connection_check", "status": "completed" if ok else "blocked", "telegram_ok": ok, "message_id": parsed.get("result", {}).get("message_id"), "blocking_conditions": [] if ok else ["telegram_send_failed"]}
    except HTTPError as exc:
        out = {"ok": False, "workflow": "daily_trading_workflow_v1", "stage": "telegram_connection_check", "status": "blocked", "blocking_conditions": [f"telegram_http_{exc.code}"], "error_tail": exc.read().decode("utf-8", errors="replace")[-800:]}
    except URLError as exc:
        out = {"ok": False, "workflow": "daily_trading_workflow_v1", "stage": "telegram_connection_check", "status": "blocked", "blocking_conditions": ["telegram_unreachable"], "error": str(exc.reason)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
