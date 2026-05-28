"""Evening selloff / close risk layer.

This script does NOT place sell orders. It prepares a close-risk review list and
requires Leader AI/human approval before any execution workflow.
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


def action_for_position(pos: dict[str, Any]) -> tuple[str, list[str]]:
    pnl_pct = num(pos.get("pnl_pct"))
    strategy = str(pos.get("strategy") or "")
    reasons: list[str] = []
    if "opening" in strategy or "day" in strategy or "scalp" in strategy:
        reasons.append("day_trading_strategy_position")
    if pnl_pct <= -1.0:
        reasons.append("loss_exceeds_intraday_stop_reference")
        return "SELL_REVIEW_REQUIRED", reasons
    if pnl_pct >= 2.0:
        reasons.append("profit_exceeds_second_take_profit_reference")
        return "PARTIAL_OR_FULL_TAKE_PROFIT_REVIEW", reasons
    if reasons:
        return "CLOSE_OR_HOLD_REVIEW", reasons
    return "HOLD_REVIEW", ["non_day_trading_or_missing_strategy"]


def main() -> int:
    blocks: list[str] = []
    alerts: list[str] = []
    review_items: list[dict[str, Any]] = []
    try:
        sb = SupabaseRestClient()
        positions = sb.get("positions", {"select": "stock_code,quantity,avg_price,current_price,pnl,pnl_pct,realized_pnl,status,strategy,last_updated", "quantity": "gt.0", "order": "pnl_pct.asc"})
    except SupabaseRestError as exc:
        blocks.append(str(exc))
        positions = []

    for pos in positions:
        if num(pos.get("quantity")) <= 0:
            continue
        action, reasons = action_for_position(pos)
        review_items.append({**pos, "recommended_action": action, "reasons": reasons, "order_execution_enabled": False})

    review_items.sort(key=lambda x: ("SELL" not in str(x.get("recommended_action")), num(x.get("pnl_pct"))))
    if not review_items and not blocks:
        alerts.append("no_open_positions_for_evening_selloff")

    out = {
        "ok": not blocks,
        "workflow": "daily_trading_workflow_v1",
        "stage": "evening_selloff_layer",
        "status": "completed" if not blocks else "blocked",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "open_position_count": len(positions),
            "review_item_count": len(review_items),
            "sell_review_required_count": sum(1 for x in review_items if "SELL" in str(x.get("recommended_action"))),
            "order_execution_enabled": False,
        },
        "review_items": review_items[:30],
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts,
        "next_actions": [
            "Leader AI 또는 사용자가 review_items를 승인하기 전 주문 실행 금지",
            "당일 데이트레이딩 포지션은 원칙적으로 장후 청산/보유 사유를 기록",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
