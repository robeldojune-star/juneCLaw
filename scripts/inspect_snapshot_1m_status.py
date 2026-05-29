"""Inspect ka10006 snapshot_1m accumulation quality.

This script is read-only and prints a standard JSON envelope. It never prints
secrets and never fabricates market data.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import SupabaseRestClient, SupabaseRestError, num  # noqa: E402

SOURCE = "kiwoom_ka10006_snapshot"
TIME_FRAME = "snapshot_1m"
STAGE = "inspect_snapshot_1m_status"


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    try:
        # Supabase may return Z or +00:00. datetime accepts +00:00.
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _date_key(value: Any) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else "unknown"


def _row_quality_error(row: dict[str, Any]) -> str | None:
    if row.get("source") != SOURCE:
        return "unexpected_source"
    if row.get("time_frame") != TIME_FRAME:
        return "unexpected_time_frame"
    open_p = num(row.get("open"))
    high_p = num(row.get("high"))
    low_p = num(row.get("low"))
    close_p = num(row.get("close"))
    if min(open_p, high_p, low_p, close_p) <= 0:
        return "non_positive_ohlc"
    if high_p < max(open_p, close_p) or low_p > min(open_p, close_p):
        return "ohlc_structure_bad"
    if _parse_ts(row.get("timestamp")) is None:
        return "invalid_timestamp"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=2)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--min-rows", type=int, default=20)
    parser.add_argument("--min-codes", type=int, default=5)
    parser.add_argument("--max-lag-minutes", type=int, default=15)
    args = parser.parse_args()

    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat(timespec="seconds")
    blocks: list[str] = []
    alerts: list[str] = []

    try:
        sb = SupabaseRestClient()
        rows = sb.get(
            "intraday_prices",
            {
                "select": "stock_code,timestamp,time_frame,source,open,high,low,close,volume,trading_value",
                "time_frame": f"eq.{TIME_FRAME}",
                "source": f"eq.{SOURCE}",
                "timestamp": f"gte.{since}",
                "order": "timestamp.desc",
                "limit": str(args.limit),
            },
            timeout=30,
        )
    except SupabaseRestError as exc:
        out = {
            "ok": False,
            "workflow": "daily_trading_workflow_v1",
            "stage": STAGE,
            "status": "blocked",
            "blocking_conditions": [str(exc)],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    by_code: dict[str, dict[str, Any]] = {}
    by_day: dict[str, int] = defaultdict(int)
    seen_keys: set[tuple[str, str]] = set()
    duplicate_keys = 0
    quality_counts: dict[str, int] = defaultdict(int)
    latest_ts: datetime | None = None
    oldest_ts: datetime | None = None

    for row in rows:
        code = str(row.get("stock_code") or "unknown")
        ts_text = str(row.get("timestamp") or "")
        key = (code, ts_text)
        if key in seen_keys:
            duplicate_keys += 1
        seen_keys.add(key)

        err = _row_quality_error(row)
        if err:
            quality_counts[err] += 1

        ts = _parse_ts(ts_text)
        if ts is not None:
            latest_ts = ts if latest_ts is None or ts > latest_ts else latest_ts
            oldest_ts = ts if oldest_ts is None or ts < oldest_ts else oldest_ts

        day = _date_key(ts_text)
        by_day[day] += 1
        item = by_code.setdefault(
            code,
            {
                "rows": 0,
                "first_timestamp": ts_text,
                "last_timestamp": ts_text,
                "days": set(),
                "latest_close": row.get("close"),
                "latest_volume": row.get("volume"),
            },
        )
        item["rows"] += 1
        item["days"].add(day)
        if ts_text < item["first_timestamp"]:
            item["first_timestamp"] = ts_text
        if ts_text > item["last_timestamp"]:
            item["last_timestamp"] = ts_text
            item["latest_close"] = row.get("close")
            item["latest_volume"] = row.get("volume")

    now_utc = datetime.now(timezone.utc)
    latest_lag_minutes = None
    if latest_ts is not None:
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=timezone.utc)
        latest_lag_minutes = round((now_utc - latest_ts.astimezone(timezone.utc)).total_seconds() / 60, 2)

    if len(rows) < args.min_rows:
        blocks.append("snapshot_1m_rows_below_minimum")
    if len(by_code) < args.min_codes:
        blocks.append("snapshot_1m_active_codes_below_minimum")
    if duplicate_keys:
        alerts.append("duplicate_stock_timestamp_rows_detected")
    if quality_counts:
        blocks.append("snapshot_1m_quality_errors_detected")
    if latest_ts is None:
        blocks.append("snapshot_1m_latest_timestamp_missing")
    elif latest_lag_minutes is not None and latest_lag_minutes > args.max_lag_minutes:
        blocks.append("snapshot_1m_latest_timestamp_stale")

    code_summary = []
    for code, item in sorted(by_code.items(), key=lambda kv: (-kv[1]["rows"], kv[0])):
        code_summary.append(
            {
                "stock_code": code,
                "rows": item["rows"],
                "days": sorted(item["days"]),
                "first_timestamp": item["first_timestamp"],
                "last_timestamp": item["last_timestamp"],
                "latest_close": item["latest_close"],
                "latest_volume": item["latest_volume"],
            }
        )

    out = {
        "ok": not blocks,
        "workflow": "daily_trading_workflow_v1",
        "stage": STAGE,
        "status": "completed" if not blocks else "blocked",
        "summary": {
            "source": SOURCE,
            "time_frame": TIME_FRAME,
            "lookback_days": args.days,
            "rows": len(rows),
            "active_codes": len(by_code),
            "days_seen": dict(sorted(by_day.items())),
            "oldest_timestamp": oldest_ts.isoformat() if oldest_ts else None,
            "latest_timestamp": latest_ts.isoformat() if latest_ts else None,
            "latest_lag_minutes": latest_lag_minutes,
            "duplicate_stock_timestamp_keys": duplicate_keys,
            "quality_error_counts": dict(sorted(quality_counts.items())),
        },
        "per_code": code_summary[:50],
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts,
        "next_actions": [
            "장중에는 latest_lag_minutes가 수집 주기보다 크게 벌어지는지 확인하세요",
            "rows/active_codes가 부족하면 Hermes cron과 trading-runner 로그를 먼저 확인하세요",
            "품질 오류가 있으면 백테스트/주문 단계는 계속 blocked로 유지하세요",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
