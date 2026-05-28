"""News/growth briefing stage for the daily trading workflow.

Current implementation is intentionally data-source conservative:
- does not fabricate news
- uses OpenDART disclosure smoke check when available
- reports missing dedicated news collector as a blocking condition
- emits Telegram-ready summary JSON
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import read_env  # noqa: E402


def run_optional_opendart_smoke() -> dict[str, object]:
    script = PROJECT_ROOT / "scripts" / "test_opendart_api.py"
    if not script.exists():
        return {"ok": False, "blocking_condition": "opendart_smoke_script_missing"}
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=90,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "blocking_condition": "opendart_smoke_failed", "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-800:],
        "blocking_condition": None if proc.returncode == 0 else "opendart_smoke_failed",
    }


def run_news_collector() -> dict[str, Any]:
    script = PROJECT_ROOT / "scripts" / "collect_news_rss.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--per-source-limit", "5", "--total-limit", "25"],
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "blocking_conditions": ["news_collector_failed"], "error": f"{type(exc).__name__}: {exc}"}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "blocking_conditions": ["news_collector_invalid_json"], "stdout_tail": proc.stdout[-1000:], "stderr_tail": proc.stderr[-800:]}
    if proc.returncode != 0 and not data.get("blocking_conditions"):
        data.setdefault("blocking_conditions", []).append("news_collector_failed")
    return data


def main() -> int:
    env = read_env()
    blocks: list[str] = []
    alerts: list[str] = []
    news = run_news_collector()
    blocks.extend(str(x) for x in news.get("blocking_conditions", []))
    data_sources = {
        "opendart_key_present": bool(env.get("OPENDART_API_KEY") or env.get("DART_API_KEY")),
        "rss_news_collector": bool(news.get("summary", {}).get("collected_item_count", 0)),
        "telegram_env_present": bool(env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID")),
    }

    if not data_sources["opendart_key_present"]:
        alerts.append("opendart_key_missing_or_not_configured")

    opendart = None
    if data_sources["opendart_key_present"]:
        opendart = run_optional_opendart_smoke()
        if opendart.get("blocking_condition"):
            alerts.append(str(opendart["blocking_condition"]))

    if not data_sources["telegram_env_present"]:
        alerts.append("telegram_env_missing_n8n_credential_required")

    items = news.get("items", [])[:15] if isinstance(news.get("items"), list) else []
    out = {
        "ok": not blocks,
        "workflow": "daily_trading_workflow_v1",
        "stage": "news_briefing_growth_analysis",
        "status": "completed" if not blocks else "blocked",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "title": "아침 뉴스/성장성 브리핑",
            "data_sources": data_sources,
            "news_item_count": len(items),
            "telegram_ready": data_sources["telegram_env_present"],
        },
        "news_items": items,
        "opendart_smoke": opendart,
        "briefing_sections": [
            f"시장/성장 뉴스 {len(items)}건 수집",
            "공시/재무 이벤트: OpenDART 키 연결 시 smoke check 포함",
            "Research AI 요약 대상: RSS items + blocking/alerts",
        ],
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts + [str(x) for x in news.get("alerts", [])],
        "next_actions": [
            "n8n Telegram credential 연결 후 news_items를 요약 전송하세요.",
            "필요하면 Naver/유료 뉴스 API를 config/news_sources.json에 추가하세요.",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
