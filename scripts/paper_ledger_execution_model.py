"""Apply a conservative paper execution model to SIMULATED orders.

This script does not call Kiwoom. It updates/prints paper-only execution assumptions:
- limit/market fill model
- one-way fee/tax bps
- one-way slippage bps
- optional price impact bps

It is intentionally conservative because mock fills do not move the real market.
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
from core.trading_mode import load_env, redacted_mode_dict, resolve_execution_mode  # noqa: E402


def adjusted_fill_price(side: str, price: float, slippage_bps: float, impact_bps: float) -> float:
    sign = 1 if side.upper() == "BUY" else -1
    return round(price * (1 + sign * (slippage_bps + impact_bps) / 10000.0), 2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--fee-bps", type=float, default=23.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--impact-bps", type=float, default=5.0)
    parser.add_argument("--fill-model", choices=["conservative_limit", "market_like"], default="conservative_limit")
    parser.add_argument("--apply", action="store_true", help="Update orders.raw_response with paper_execution_model. Default is dry-run.")
    args = parser.parse_args()

    mode = resolve_execution_mode(purpose="paper", env=load_env(PROJECT_ROOT / ".env"))
    blocks: list[str] = []
    alerts: list[str] = []
    if not mode.can_write_simulated_orders or mode.can_call_real_order_api:
        blocks.append("paper_ledger_mode_guard_failed")

    rows: list[dict[str, Any]] = []
    updated = 0
    modeled: list[dict[str, Any]] = []
    try:
        sb = SupabaseRestClient()
        rows = sb.get(
            "orders",
            {
                "select": "order_id,stock_code,order_type,quantity,price,status,strategy,raw_response,created_at",
                "status": "eq.SIMULATED",
                "order": "created_at.desc",
                "limit": str(args.limit),
            },
            timeout=60,
        )
    except SupabaseRestError as exc:
        blocks.append(f"orders_query_failed:{exc}")
        sb = None

    for order in rows:
        side = str(order.get("order_type") or "BUY")
        price = float(num(order.get("price")))
        qty = int(num(order.get("quantity")))
        if price <= 0 or qty <= 0:
            alerts.append(f"{order.get('order_id')}:invalid_price_or_quantity")
            continue
        fill_price = adjusted_fill_price(side, price, args.slippage_bps, args.impact_bps)
        gross_value = fill_price * qty
        fee = round(gross_value * args.fee_bps / 10000.0, 2)
        estimated_cash_effect = round(gross_value + fee, 2) if side.upper() == "BUY" else round(gross_value - fee, 2)
        model = {
            "fill_model": args.fill_model,
            "assumed_fill_price": fill_price,
            "reference_signal_price": price,
            "quantity": qty,
            "gross_value": round(gross_value, 2),
            "fee_bps_one_way": args.fee_bps,
            "slippage_bps_one_way": args.slippage_bps,
            "impact_bps_one_way": args.impact_bps,
            "estimated_fee": fee,
            "estimated_cash_effect": estimated_cash_effect,
            "mode": "paper_only_no_kiwoom_order_api",
            "modeled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        modeled.append({"order_id": order.get("order_id"), "stock_code": order.get("stock_code"), "paper_execution_model": model})
        if args.apply and sb is not None:
            raw = order.get("raw_response") if isinstance(order.get("raw_response"), dict) else {}
            raw["paper_execution_model"] = model
            try:
                replacement = dict(order)
                replacement["raw_response"] = raw
                res = sb.upsert_rows("orders", [replacement], on_conflict="order_id", timeout=60)
                updated += len(res)
            except SupabaseRestError as exc:
                alerts.append(f"{order.get('order_id')}:update_failed:{exc}")

    if not rows and not blocks:
        alerts.append("no_simulated_orders_found")

    out = {
        "ok": not blocks,
        "stage": "paper_ledger_execution_model",
        "status": "completed" if not blocks else "blocked",
        "summary": {
            "dry_run": not args.apply,
            "orders_seen": len(rows),
            "orders_modeled": len(modeled),
            "orders_updated": updated,
            "fee_bps_one_way": args.fee_bps,
            "slippage_bps_one_way": args.slippage_bps,
            "impact_bps_one_way": args.impact_bps,
            "execution_mode": redacted_mode_dict(mode),
        },
        "modeled_orders": modeled[:20],
        "blocking_conditions": blocks,
        "alerts": alerts,
        "next_actions": [
            "실제 Kiwoom 주문 API는 호출하지 않습니다.",
            "paper PnL은 assumed_fill_price/fee/slippage/impact 기준으로 계산하세요.",
            "real pilot 전에는 미체결/부분체결/호가충격을 별도 shadow mode로 기록하세요.",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
