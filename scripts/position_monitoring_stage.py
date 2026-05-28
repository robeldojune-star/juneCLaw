"""Position/order monitoring stages for daily trading workflow.

Stages:
- post_opening_monitoring
- midday_position_review
- pre_close_risk_review

Reads positions/orders/signals from Supabase REST and emits standardized JSON.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import SupabaseRestClient, SupabaseRestError, num  # noqa: E402

STAGES = {"post_opening_monitoring", "midday_position_review", "pre_close_risk_review"}


def risk_flags_for_position(pos: dict[str, Any], stage: str) -> list[str]:
    flags: list[str] = []
    pnl_pct = num(pos.get("pnl_pct"))
    qty = num(pos.get("quantity"))
    if qty <= 0:
        return flags
    if pnl_pct <= -1.0:
        flags.append("stop_loss_review_required")
    if pnl_pct >= 2.0:
        flags.append("take_profit_review_required")
    if stage == "pre_close_risk_review" and qty > 0:
        flags.append("day_trade_close_or_hold_decision_required")
    return flags


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=sorted(STAGES))
    args = parser.parse_args()

    today = datetime.now(timezone.utc).date().isoformat()
    blocks: list[str] = []
    alerts: list[str] = []
    positions: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []

    try:
        sb = SupabaseRestClient()
        positions = sb.get("positions", {"select": "stock_code,quantity,avg_price,current_price,pnl,pnl_pct,realized_pnl,status,strategy,updated_at", "quantity": "gt.0", "order": "pnl_pct.asc"})
        orders = sb.get("orders", {"select": "stock_code,order_type,quantity,price,filled_price,filled_quantity,status,strategy,created_at", "created_at": f"gte.{today}T00:00:00Z", "order": "created_at.desc", "limit": "100"})
        signals = sb.get("trading_signals", {"select": "stock_code,signal_type,score,strategy,executed,signal_date", "signal_date": f"gte.{today}T00:00:00Z", "order": "signal_date.desc", "limit": "100"})
    except SupabaseRestError as exc:
        blocks.append(str(exc))

    open_positions = [p for p in positions if num(p.get("quantity")) > 0]
    flagged_positions = []
    for p in open_positions:
        flags = risk_flags_for_position(p, args.stage)
        if flags:
            flagged_positions.append({**p, "risk_flags": flags})

    pending_orders = [o for o in orders if str(o.get("status") or "").upper() in {"PENDING", "ACCEPTED", "PARTIAL"}]
    failed_orders = [o for o in orders if str(o.get("status") or "").upper() in {"FAILED", "REJECTED", "CANCELLED"}]
    buy_signals = [s for s in signals if s.get("signal_type") == "BUY"]
    executed_signals = [s for s in signals if s.get("executed")]

    if pending_orders:
        alerts.append("pending_orders_exist")
    if failed_orders:
        alerts.append("failed_or_rejected_orders_exist")
    if flagged_positions:
        alerts.append("position_risk_flags_exist")
    if args.stage == "post_opening_monitoring" and buy_signals and not executed_signals:
        alerts.append("buy_signals_not_executed_after_open")
    if args.stage in {"midday_position_review", "pre_close_risk_review"} and not open_positions:
        alerts.append("no_open_positions")

    out = {
        "ok": not blocks,
        "workflow": "daily_trading_workflow_v1",
        "stage": args.stage,
        "status": "completed" if not blocks else "blocked",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "open_position_count": len(open_positions),
            "pending_order_count": len(pending_orders),
            "failed_order_count": len(failed_orders),
            "today_signal_count": len(signals),
            "today_buy_signal_count": len(buy_signals),
            "today_executed_signal_count": len(executed_signals),
            "flagged_position_count": len(flagged_positions),
            "total_unrealized_pnl": round(sum(num(p.get("pnl")) for p in open_positions), 2),
        },
        "flagged_positions": flagged_positions[:20],
        "pending_orders": pending_orders[:20],
        "failed_orders": failed_orders[:20],
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts,
        "next_actions": [
            "alerts가 있으면 Telegram으로 보고하고 Leader AI 승인 전 자동 주문을 막으세요.",
            "pre_close 단계에서는 데이트레이딩 포지션 청산/보유 결정을 기록하세요.",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
