"""Backtest skeleton for 10m/30m opening range variants.

This script does not generate fake data. It only reports readiness and the
blocking conditions until real intraday history is loaded into Supabase.
"""
from __future__ import annotations

import json


def main() -> int:
    out = {
        "ok": False,
        "workflow": "backtest_opening_range",
        "strategy_id": "opening_multi_factor_v1",
        "status": "blocked_until_real_intraday_history_available",
        "variants": {
            "opening_10m": {
                "trades": 0,
                "win_rate": None,
                "avg_return_pct": None,
                "max_drawdown_pct": None,
            },
            "opening_30m": {
                "trades": 0,
                "win_rate": None,
                "avg_return_pct": None,
                "max_drawdown_pct": None,
            },
        },
        "blocking_conditions": [
            "need_90_trading_days_intraday_prices",
            "need_market_hours_validation_for_ka10005_timeframe",
            "need_transaction_cost_and_slippage_assumptions",
        ],
        "next_action": "Collect real Kiwoom intraday bars into intraday_prices, then implement metric calculation without fake/sample data.",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
