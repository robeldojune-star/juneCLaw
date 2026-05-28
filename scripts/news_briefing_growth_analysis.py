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


def main() -> int:
    env = read_env()
    blocks: list[str] = []
    alerts: list[str] = []
    data_sources = {
        "opendart_key_present": bool(env.get("OPENDART_API_KEY") or env.get("DART_API_KEY")),
        "dedicated_news_collector": False,
        "telegram_env_present": bool(env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID")),
    }

    if not data_sources["dedicated_news_collector"]:
        blocks.append("news_collector_not_implemented")
    if not data_sources["opendart_key_present"]:
        blocks.append("opendart_key_missing_or_not_configured")

    opendart = None
    if data_sources["opendart_key_present"]:
        opendart = run_optional_opendart_smoke()
        if opendart.get("blocking_condition"):
            blocks.append(str(opendart["blocking_condition"]))

    if not data_sources["telegram_env_present"]:
        alerts.append("telegram_env_missing_n8n_credential_required")

    out = {
        "ok": not blocks,
        "workflow": "daily_trading_workflow_v1",
        "stage": "news_briefing_growth_analysis",
        "status": "completed" if not blocks else "blocked",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "title": "아침 뉴스/성장성 브리핑",
            "data_sources": data_sources,
            "message": "전용 뉴스 수집기가 구현되기 전까지 OpenDART/기존 리포트 기반 점검만 수행합니다.",
            "telegram_ready": data_sources["telegram_env_present"],
        },
        "opendart_smoke": opendart,
        "briefing_sections": [
            "시장 주요 뉴스: dedicated collector 필요",
            "공시/재무 이벤트: OpenDART 연결 후 자동화",
            "성장 테마 후보: 뉴스 collector + Research AI 요약 연결 필요",
        ],
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts,
        "next_actions": [
            "뉴스 소스/RSS/API를 확정하면 collector를 연결하세요.",
            "Telegram은 n8n credential 또는 TELEGRAM_BOT_TOKEN/CHAT_ID로 연결하세요.",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
