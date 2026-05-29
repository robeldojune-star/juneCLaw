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
from core.supabase_rest import SupabaseRestClient, SupabaseRestError  # noqa: E402


def _price(value: Any) -> int | None:
    return clean_int(value, abs_value=True)


def _load_manual_fujimoto_inputs(stock_code: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load analyst-reviewed manual inputs for fujimoto aux filter.

    File path: data/review/fujimoto_inputs.json
    Shape:
    {
      "005930": {
        "operating_income_positive": true,
        "earnings_trend_ok": true,
        "stage_entry_ready": false,
        "review_note": "..."
      }
    }
    """
    review_path = PROJECT_ROOT / "data" / "review" / "fujimoto_inputs.json"
    meta: dict[str, Any] = {
        "path": str(review_path),
        "exists": review_path.exists(),
        "loaded": False,
        "errors": [],
    }
    if not review_path.exists():
        return {}, meta

    try:
        raw = json.loads(review_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        meta["errors"].append(f"manual_review_json_invalid: {type(exc).__name__}: {exc}")
        return {}, meta

    if not isinstance(raw, dict):
        meta["errors"].append("manual_review_json_not_object")
        return {}, meta

    item = raw.get(stock_code)
    if not isinstance(item, dict):
        meta["errors"].append("manual_review_stock_entry_missing")
        return {}, meta

    meta["loaded"] = True
    return item, meta


def _load_latest_daily_rsi(stock_code: str) -> tuple[float | None, dict[str, Any]]:
    meta: dict[str, Any] = {"source": "technical_indicators.daily", "loaded": False, "error": None}
    try:
        sb = SupabaseRestClient()
        rows = sb.get(
            "technical_indicators",
            {
                "select": "date,rsi",
                "stock_code": f"eq.{stock_code}",
                "time_frame": "eq.daily",
                "order": "date.desc",
                "limit": "1",
            },
            timeout=20,
        )
    except SupabaseRestError as exc:
        meta["error"] = str(exc)
        return None, meta

    if not rows:
        meta["error"] = "daily_rsi_not_found"
        return None, meta

    try:
        raw_rsi = rows[0].get("rsi")
        rsi = float(raw_rsi) if raw_rsi is not None else None
    except (TypeError, ValueError):
        meta["error"] = "daily_rsi_invalid_type"
        return None, meta

    meta["loaded"] = rsi is not None
    meta["date"] = rows[0].get("date")
    return rsi, meta


def _load_snapshot_bars(stock_code: str, limit: int) -> tuple[list[OpeningBar], dict[str, Any]]:
    """Load validated ka10006 snapshot_1m rows from Supabase, oldest-first."""
    meta: dict[str, Any] = {"source": "intraday_prices.snapshot_1m", "error": None, "rows_count": 0}
    try:
        sb = SupabaseRestClient()
        rows = sb.get(
            "intraday_prices",
            {
                "select": "timestamp,open,high,low,close,volume,source,time_frame",
                "stock_code": f"eq.{stock_code}",
                "time_frame": "eq.snapshot_1m",
                "source": "eq.kiwoom_ka10006_snapshot",
                "order": "timestamp.desc",
                "limit": str(limit),
            },
            timeout=20,
        )
    except SupabaseRestError as exc:
        meta["error"] = str(exc)
        return [], meta

    bars: list[OpeningBar] = []
    for row in reversed(rows):
        open_p = _price(row.get("open"))
        high_p = _price(row.get("high"))
        low_p = _price(row.get("low"))
        close_p = _price(row.get("close"))
        if open_p is None or high_p is None or low_p is None or close_p is None:
            continue
        bars.append(OpeningBar(open=open_p, high=high_p, low=low_p, close=close_p, volume=_price(row.get("volume"))))
    meta["rows_count"] = len(rows)
    meta["bars_count"] = len(bars)
    meta["latest_timestamp"] = rows[0].get("timestamp") if rows else None
    return bars, meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-code", default="005930")
    parser.add_argument("--base-dt", default=None, help="YYYYMMDD for previous daily chart lookup; default uses latest available from Kiwoom")
    parser.add_argument("--limit-bars", type=int, default=30)
    args = parser.parse_args()

    client = KiwoomAPIClient.from_env(PROJECT_ROOT / ".env")
    market = MarketDataService(client)

    snapshot = market.get_current_session_snapshot(args.stock_code)
    bars, snapshot_meta = _load_snapshot_bars(args.stock_code, args.limit_bars)

    # Safety guard: do not use ka10005 as minute bars anymore. It was verified
    # to return daily-like rows in this environment, so opening strategy must be
    # based on accumulated ka10006 snapshot_1m rows or remain blocked.
    pre_blocks: list[str] = []
    if not bars:
        pre_blocks.append("snapshot_1m_bars_not_accumulated")

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

    manual_inputs, manual_meta = _load_manual_fujimoto_inputs(args.stock_code)
    daily_rsi, rsi_meta = _load_latest_daily_rsi(args.stock_code)

    latest_trading_value = _price(snapshot.get("trde_prica"))
    turnover = float(latest_trading_value) if latest_trading_value is not None else None

    operating_income_positive = manual_inputs.get("operating_income_positive")
    earnings_trend_ok = manual_inputs.get("earnings_trend_ok")
    stage_entry_ready = manual_inputs.get("stage_entry_ready")

    inp = OpeningStrategyInput(
        stock_code=args.stock_code,
        today_open=_price(snapshot.get("open_pric")),
        current_price=_price(snapshot.get("close_pric")) or _price(snapshot.get("cur_prc")),
        yesterday_high=previous.high if previous else None,
        yesterday_low=previous.low if previous else None,
        bars=bars,
        financial_filter_passed=(operating_income_positive is True),
        rsi=daily_rsi,
        turnover=turnover,
        operating_income_positive=operating_income_positive,
        earnings_trend_ok=earnings_trend_ok,
        stage_entry_ready=stage_entry_ready,
    )
    score = score_opening_multi_factor(inp)

    review_required: list[str] = []
    if not manual_meta.get("loaded"):
        review_required.append("manual_fujimoto_review_missing")
    if daily_rsi is None:
        review_required.append("daily_rsi_review_needed")

    blocking_conditions = list(dict.fromkeys(pre_blocks + score.blocking_conditions))
    out = {
        "ok": not blocking_conditions,
        "workflow": "run_opening_strategy_research",
        "strategy_id": score.strategy_id,
        "stock_code": args.stock_code,
        "signal_type": score.signal_type,
        "score": score.total_score,
        "score_details": score.score_details,
        "blocking_conditions": blocking_conditions,
        "reason": score.reason,
        "data_quality": {
            "snapshot_keys": sorted(snapshot.keys())[:80],
            "bars_count": len(bars),
            "snapshot_1m_meta": snapshot_meta,
            "daily_rows_count": len(daily),
            "daily_error": daily_error,
            "daily_rsi_meta": rsi_meta,
            "turnover_from_snapshot": turnover,
            "manual_fujimoto_review": {
                "meta": manual_meta,
                "values": {
                    "operating_income_positive": operating_income_positive,
                    "earnings_trend_ok": earnings_trend_ok,
                    "stage_entry_ready": stage_entry_ready,
                    "review_note": manual_inputs.get("review_note") if isinstance(manual_inputs, dict) else None,
                },
            },
            "review_required": review_required,
            "note": "opening strategy uses accumulated ka10006 snapshot_1m rows; ka10005 is not used as minute data",
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
