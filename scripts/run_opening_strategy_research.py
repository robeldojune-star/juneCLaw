"""Run opening_multi_factor_v1 against real Kiwoom read APIs.

This is a Research AI bridge script: it prints a JSON result that n8n can parse.
No orders are sent from this script.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.kiwoom_client import KiwoomAPIClient, clean_int  # noqa: E402
from core.market_data_service import MarketDataService  # noqa: E402
from core.opening_strategy import OpeningBar, OpeningStrategyInput, score_opening_multi_factor  # noqa: E402


def _price(value: Any) -> int | None:
    return clean_int(value, abs_value=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-code", default="005930")
    parser.add_argument("--base-dt", default=None, help="YYYYMMDD for previous daily chart lookup; default uses latest available from Kiwoom")
    parser.add_argument("--limit-bars", type=int, default=30)
    args = parser.parse_args()

    client = KiwoomAPIClient.from_env(PROJECT_ROOT / ".env")
    market = MarketDataService(client)

    snapshot = market.get_current_session_snapshot(args.stock_code)
    bars_raw = market.get_intraday_ohlcv(args.stock_code)[: args.limit_bars]
    bars = [OpeningBar(open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume) for b in bars_raw]

    # Use ka10081 latest rows to infer previous high/low. The response is sorted latest-first in verified smoke tests.
    # If unavailable, the strategy will report blocking conditions rather than fabricating data.
    daily = []
    try:
        from datetime import datetime
        base_dt = args.base_dt or datetime.now().strftime("%Y%m%d")
        daily = market.get_daily_prices(args.stock_code, base_dt=base_dt)
    except Exception as exc:  # noqa: BLE001
        daily_error = f"{type(exc).__name__}: {exc}"
    else:
        daily_error = None

    previous = daily[1] if len(daily) >= 2 else (daily[0] if daily else None)

    inp = OpeningStrategyInput(
        stock_code=args.stock_code,
        today_open=_price(snapshot.get("open_pric")),
        current_price=_price(snapshot.get("close_pric")) or _price(snapshot.get("cur_prc")),
        yesterday_high=previous.high if previous else None,
        yesterday_low=previous.low if previous else None,
        bars=bars,
        financial_filter_passed=None,
        rsi=None,
    )
    score = score_opening_multi_factor(inp)
    out = {
        "ok": True,
        "workflow": "run_opening_strategy_research",
        "strategy_id": score.strategy_id,
        "stock_code": args.stock_code,
        "signal_type": score.signal_type,
        "score": score.total_score,
        "score_details": score.score_details,
        "blocking_conditions": score.blocking_conditions,
        "reason": score.reason,
        "data_quality": {
            "snapshot_keys": sorted(snapshot.keys())[:80],
            "bars_count": len(bars),
            "daily_rows_count": len(daily),
            "daily_error": daily_error,
            "note": "ka10005 OHLCV structure verified; exact 1m/5m semantics still need market-hours validation",
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
