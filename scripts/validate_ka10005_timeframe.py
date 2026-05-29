"""Validate ka10005 timeframe semantics during market hours.

Uses real Kiwoom data only. No mock rows are generated.
The script checks:
- monotonic date/time sequence
- unique bar keys
- non-negative OHLCV values
- same-day density heuristic (whether bars likely minute-level)

It returns blocked status outside market hours unless --allow-offhours is used.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.kiwoom_client import KiwoomAPIClient, clean_int  # noqa: E402
from core.market_data_service import MarketDataService  # noqa: E402


def _extract_time(raw: dict) -> str | None:
    """Extract an intraday HHMMSS value when the response exposes one.

    Important: ka10005 often returns ``date`` as a plain YYYYMMDD daily bar.
    Treating that 8-digit date as a time made bogus keys like
    ``20260529260529`` and incorrectly implied minute data. Only explicit time
    fields, or combined datetime values in non-date keys, should become HHMMSS.
    """
    for key in ("time", "tm", "trde_tm", "cntr_tm", "stck_cntg_hour", "dt"):
        val = str(raw.get(key) or "").strip()
        if not val:
            continue
        digits = re.sub(r"\D", "", val)
        if len(digits) >= 12:
            return digits[-6:]
        if len(digits) == 6:
            return digits
    return None


def _bar_key(raw: dict) -> str:
    d = str(raw.get("date") or raw.get("dt") or "").strip()
    t = _extract_time(raw) or "000000"
    digits = re.sub(r"\D", "", d)
    if len(digits) < 8:
        digits = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
    return digits[:8] + t


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-code", default="005930")
    parser.add_argument("--min-bars", type=int, default=20)
    parser.add_argument("--allow-offhours", action="store_true")
    args = parser.parse_args()

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    hhmm = now_kst.hour * 100 + now_kst.minute
    market_hours = 900 <= hhmm <= 1535 and now_kst.weekday() < 5

    blocks: list[str] = []
    alerts: list[str] = []
    if not market_hours and not args.allow_offhours:
        blocks.append("outside_market_hours")

    client = KiwoomAPIClient.from_env(PROJECT_ROOT / ".env")
    market = MarketDataService(client)

    try:
        rows = market.get_intraday_ohlcv_raw(args.stock_code)
    except Exception as exc:  # noqa: BLE001
        out = {
            "ok": False,
            "workflow": "daily_trading_workflow_v1",
            "stage": "ka10005_timeframe_validation",
            "status": "blocked",
            "blocking_conditions": ["ka10005_api_failed"],
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    keys = [_bar_key(r) for r in rows if isinstance(r, dict)]
    unique_keys = len(set(keys))
    duplicate_count = max(len(keys) - unique_keys, 0)
    descending = all(keys[i] >= keys[i + 1] for i in range(len(keys) - 1)) if len(keys) > 1 else True

    ohlcv_bad = 0
    same_day = now_kst.strftime("%Y%m%d")
    today_count = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        d = re.sub(r"\D", "", str(r.get("date") or ""))[:8]
        if d == same_day:
            today_count += 1
        vals = [clean_int(r.get("open_pric"), abs_value=True), clean_int(r.get("high_pric"), abs_value=True), clean_int(r.get("low_pric"), abs_value=True), clean_int(r.get("close_pric"), abs_value=True), clean_int(r.get("trde_qty"), abs_value=True)]
        if any(v is None or v < 0 for v in vals):
            ohlcv_bad += 1

    if len(rows) < args.min_bars:
        blocks.append("ka10005_not_enough_bars")
    if duplicate_count > 0:
        blocks.append("ka10005_duplicate_bar_keys")
    if not descending:
        alerts.append("ka10005_bar_order_not_descending")
    if ohlcv_bad > 0:
        blocks.append("ka10005_invalid_ohlcv_values")

    explicit_time_count = sum(1 for r in rows if isinstance(r, dict) and _extract_time(r))
    # Minute-like density heuristic (for same-day bars): require explicit time keys
    # and enough same-day rows. Daily-only ka10005 responses must not be treated as 1m data.
    minute_like = explicit_time_count >= args.min_bars and today_count >= min(10, args.min_bars)
    if not minute_like:
        alerts.append("ka10005_minute_density_low")
        alerts.append("ka10005_response_currently_looks_daily_not_intraday")
        if market_hours or args.allow_offhours:
            blocks.append("ka10005_timeframe_not_minute_like")

    out = {
        "ok": not blocks,
        "workflow": "daily_trading_workflow_v1",
        "stage": "ka10005_timeframe_validation",
        "status": "completed" if not blocks else "blocked",
        "summary": {
            "stock_code": args.stock_code,
            "market_hours": market_hours,
            "rows": len(rows),
            "today_bar_count": today_count,
            "explicit_time_bar_count": explicit_time_count,
            "unique_bar_keys": unique_keys,
            "duplicate_bar_count": duplicate_count,
            "ohlcv_bad_count": ohlcv_bad,
            "minute_like_density": minute_like,
        },
        "sample_bar_keys": keys[:10],
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts,
        "next_actions": [
            "장중(09:00~15:30) 2~3회 반복 실행 후 minute_like_density 안정성 확인",
            "검증 통과 전 자동 주문 guard를 해제하지 마세요",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
