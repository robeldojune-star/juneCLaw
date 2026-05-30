"""Inspect Kiwoom ka10080 historical 1-minute bar integrity.

Checks real Supabase intraday_prices rows only. No synthetic fill.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, time
import json
from pathlib import Path
import sys
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import SupabaseRestClient, SupabaseRestError, num  # noqa: E402

SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"
KST = ZoneInfo("Asia/Seoul")


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        return dt.astimezone(KST)
    except ValueError:
        return None


def fetch_rows(sb: SupabaseRestClient, codes: list[str], page_size: int) -> list[dict[str, Any]]:
    all_rows: list[dict[str, Any]] = []
    for code in codes:
        offset = 0
        while True:
            page = sb.get(
                "intraday_prices",
                {
                    "select": "stock_code,timestamp,time_frame,source,open,high,low,close,volume,trading_value",
                    "stock_code": f"eq.{code}",
                    "source": f"eq.{SOURCE}",
                    "time_frame": f"eq.{TIME_FRAME}",
                    "order": "timestamp.asc",
                    "limit": str(page_size),
                    "offset": str(offset),
                },
                timeout=60,
            )
            all_rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
            if offset > 500000:
                break
    return all_rows


def row_error(row: dict[str, Any]) -> str | None:
    if row.get("source") != SOURCE:
        return "unexpected_source"
    if row.get("time_frame") != TIME_FRAME:
        return "unexpected_time_frame"
    ts = parse_ts(row.get("timestamp"))
    if ts is None:
        return "invalid_timestamp"
    o, h, l, c = num(row.get("open")), num(row.get("high")), num(row.get("low")), num(row.get("close"))
    if min(o, h, l, c) <= 0:
        return "non_positive_ohlc"
    if h < max(o, c) or l > min(o, c):
        return "ohlc_structure_bad"
    volume = row.get("volume")
    if volume is not None and num(volume) < 0:
        return "negative_volume"
    return None


def session_bucket(ts: datetime) -> str:
    t = ts.time()
    if time(9, 0) <= t <= time(15, 20) or t == time(15, 30):
        return "regular"
    if time(15, 21) <= t <= time(15, 29):
        return "closing_call_auction_gap"
    if time(15, 31) <= t <= time(15, 40):
        return "closing_or_after_session"
    return "outside_regular"


def minute_range(day: str, start: str, end: str) -> list[str]:
    cur = datetime.fromisoformat(f"{day}T{start}:00+09:00")
    finish = datetime.fromisoformat(f"{day}T{end}:00+09:00")
    out: list[str] = []
    while cur <= finish:
        out.append(cur.strftime("%H:%M"))
        cur = cur.replace(minute=cur.minute + 1) if cur.minute < 59 else cur.replace(hour=cur.hour + 1, minute=0)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-codes", nargs="+", default=["005930", "000660", "035420", "005380", "068270"])
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--min-regular-bars", type=int, default=300)
    parser.add_argument("--max-missing-regular-minutes", type=int, default=15)
    args = parser.parse_args()

    blocks: list[str] = []
    alerts: list[str] = []
    try:
        sb = SupabaseRestClient()
        rows = fetch_rows(sb, args.stock_codes, args.page_size)
    except SupabaseRestError as exc:
        print(json.dumps({"ok": False, "stage": "inspect_ka10080_minute_integrity", "blocking_conditions": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2

    by_code_day: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    quality_counts: dict[str, int] = defaultdict(int)
    seen: set[tuple[str, str]] = set()
    duplicate_keys = 0
    outside_regular = 0
    after_session = 0
    closing_call_gap_rows = 0

    for row in rows:
        code = str(row.get("stock_code") or "")
        ts = parse_ts(row.get("timestamp"))
        if ts is None:
            quality_counts["invalid_timestamp"] += 1
            continue
        key = (code, ts.isoformat())
        if key in seen:
            duplicate_keys += 1
        seen.add(key)
        err = row_error(row)
        if err:
            quality_counts[err] += 1
        bucket = session_bucket(ts)
        if bucket == "outside_regular":
            outside_regular += 1
        elif bucket == "closing_call_auction_gap":
            closing_call_gap_rows += 1
        elif bucket == "closing_or_after_session":
            after_session += 1
        by_code_day[(code, ts.strftime("%Y-%m-%d"))].append(row)

    day_summaries = []
    for (code, day), day_rows in sorted(by_code_day.items()):
        times = []
        regular_times = []
        for row in day_rows:
            ts = parse_ts(row.get("timestamp"))
            if ts is None:
                continue
            hhmm = ts.strftime("%H:%M")
            times.append(hhmm)
            if session_bucket(ts) == "regular":
                regular_times.append(hhmm)
        unique_regular = sorted(set(regular_times))
        expected = minute_range(day, "09:00", "15:20") + ["15:30"]
        opening_expected = minute_range(day, "09:00", "09:30")
        opening_missing = sorted(set(opening_expected) - set(unique_regular))
        missing = sorted(set(expected) - set(unique_regular))
        duplicate_minutes = len(regular_times) - len(unique_regular)
        row_count = len(day_rows)
        regular_count = len(unique_regular)
        summary = {
            "stock_code": code,
            "date": day,
            "rows": row_count,
            "regular_unique_minutes": regular_count,
            "first_time": min(times) if times else None,
            "last_time": max(times) if times else None,
            "missing_regular_minutes": len(missing),
            "missing_regular_sample": missing[:20],
            "opening_09_00_09_30_complete": not opening_missing,
            "opening_missing_minutes": len(opening_missing),
            "opening_missing_sample": opening_missing[:20],
            "duplicate_regular_minutes": duplicate_minutes,
        }
        day_summaries.append(summary)
        if regular_count < args.min_regular_bars:
            alerts.append(f"{code}_{day}_regular_bars_below_{args.min_regular_bars}:{regular_count}")
        if len(missing) > args.max_missing_regular_minutes:
            alerts.append(f"{code}_{day}_missing_regular_minutes:{len(missing)}")
        if opening_missing:
            alerts.append(f"{code}_{day}_opening_09_00_09_30_missing:{len(opening_missing)}")
        if duplicate_minutes:
            alerts.append(f"{code}_{day}_duplicate_regular_minutes:{duplicate_minutes}")

    if not rows:
        blocks.append("no_ka10080_minute_rows")
    if duplicate_keys:
        blocks.append("duplicate_stock_timestamp_keys")
    if quality_counts:
        blocks.append("ka10080_quality_errors_detected")

    by_code = defaultdict(int)
    for row in rows:
        by_code[str(row.get("stock_code") or "unknown")] += 1

    out = {
        "ok": not blocks,
        "stage": "inspect_ka10080_minute_integrity",
        "status": "completed" if not blocks else "blocked",
        "summary": {
            "source": SOURCE,
            "time_frame": TIME_FRAME,
            "rows": len(rows),
            "stock_rows": dict(sorted(by_code.items())),
            "stock_day_count": len(day_summaries),
            "duplicate_stock_timestamp_keys": duplicate_keys,
            "quality_error_counts": dict(sorted(quality_counts.items())),
            "outside_regular_rows": outside_regular,
            "closing_call_auction_gap_rows": closing_call_gap_rows,
            "closing_or_after_session_rows": after_session,
            "regular_day_min_bars_threshold": args.min_regular_bars,
            "expected_regular_definition": "09:00~15:20 plus 15:30; 15:21~15:29 is treated as closing-call-auction gap",
        },
        "day_summaries": day_summaries,
        "blocking_conditions": blocks,
        "alerts": alerts[:200],
        "next_actions": [
            "missing_regular_minutes가 크면 ka10080 연속조회/요청 범위를 보강하세요.",
            "차트에서 캔들 간 큰 시간 공백이 있는지 시각 확인하세요.",
            "15:31~15:35 체결/종가 관련 row는 Kiwoom 차트 특성일 수 있으므로 regular session과 별도 집계하세요.",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
