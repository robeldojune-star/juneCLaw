"""Compress pre-market trading candidates to a small watchlist.

Reads real trading_signals/kospi_top50 rows from Supabase REST. No fake candidates.
Outputs standardized JSON for n8n.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import SupabaseRestClient, SupabaseRestError, num  # noqa: E402


def main() -> int:
    blocks: list[str] = []
    alerts: list[str] = []
    candidates: list[dict[str, Any]] = []
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        sb = SupabaseRestClient()
        signals = sb.get(
            "trading_signals",
            {
                "select": "stock_code,signal_type,score,signal_strength,price,reason,strategy,signal_date,score_details,executed",
                "signal_date": f"gte.{today}T00:00:00Z",
                "order": "score.desc",
                "limit": "100",
            },
        )
        kospi = sb.get("kospi_top50", {"select": "stock_code,stock_name,rank,market_cap,sector,is_active", "is_active": "eq.true"})
        master = {r.get("stock_code"): r for r in kospi}
    except SupabaseRestError as exc:
        blocks.append(str(exc))
        signals = []
        master = {}

    buy_like = [s for s in signals if str(s.get("signal_type")) == "BUY"]
    if not signals:
        blocks.append("no_today_signals_found_for_candidate_compression")
    if not buy_like:
        alerts.append("no_buy_signals_today")

    for sig in buy_like:
        code = str(sig.get("stock_code") or "")
        m = master.get(code, {})
        score = num(sig.get("score") or sig.get("signal_strength"))
        rank_penalty = min(num(m.get("rank")) * 0.1, 5) if m.get("rank") else 0
        compressed_score = max(score - rank_penalty, 0)
        candidates.append(
            {
                "stock_code": code,
                "stock_name": m.get("stock_name"),
                "rank": m.get("rank"),
                "sector": m.get("sector"),
                "signal_score": score,
                "compressed_score": round(compressed_score, 4),
                "price": sig.get("price"),
                "strategy": sig.get("strategy"),
                "reason": sig.get("reason"),
                "blocking_conditions": [] if score >= 60 else ["score_below_buy_threshold"],
            }
        )
    candidates.sort(key=lambda x: num(x.get("compressed_score")), reverse=True)
    top = candidates[:10]
    if not top and not blocks:
        blocks.append("candidate_watchlist_empty")

    out = {
        "ok": not blocks,
        "workflow": "daily_trading_workflow_v1",
        "stage": "candidate_compression_layer",
        "status": "completed" if not blocks else "blocked",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "today_signal_count": len(signals),
            "buy_signal_count": len(buy_like),
            "candidate_count": len(top),
            "target_count": "TOP 5~10",
        },
        "candidates": top,
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts,
        "next_actions": ["09:00 이후에는 이 후보군에 대해서만 스냅샷/OR10/OR30을 평가하세요."],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
