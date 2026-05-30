"""Inspect BUY signals whose next ka10080 minute trading day is missing.

Read-only diagnostic for Fujimoto 1-2-6 signal-mode backtest.
Does not print secrets and does not modify DB.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import read_env  # noqa: E402

SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"
KST = timezone(timedelta(hours=9))


def parse_day(text: str | None) -> date | None:
    return datetime.fromisoformat(text[:10]).date() if text else None


def fetch_signal_dates(cur: Any, start: date | None, end: date | None) -> list[date]:
    params: list[Any] = []
    where = ["signal_type='BUY'"]
    if start:
        where.append("signal_date::date >= %s")
        params.append(start)
    if end:
        where.append("signal_date::date <= %s")
        params.append(end)
    cur.execute(f"select distinct signal_date::date from trading_signals where {' and '.join(where)} order by 1", params)
    return [row[0] for row in cur.fetchall()]


def fetch_buy_signals(cur: Any, signal_day: date, limit: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        select id, stock_code, signal_date, coalesce(score, signal_strength, 0) as score
        from trading_signals
        where signal_type='BUY' and signal_date::date=%s
        order by coalesce(score, signal_strength, 0) desc, stock_code asc
        limit %s
        """,
        (signal_day, limit),
    )
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def next_minute_day(cur: Any, stock_code: str, signal_day: date) -> date | None:
    cur.execute(
        """
        select min((timestamp at time zone 'Asia/Seoul')::date)
        from intraday_prices
        where stock_code=%s and source=%s and time_frame=%s
          and (timestamp at time zone 'Asia/Seoul')::date > %s
        """,
        (stock_code, SOURCE, TIME_FRAME, signal_day),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def minute_coverage(cur: Any, stock_code: str) -> dict[str, Any]:
    cur.execute(
        """
        select min((timestamp at time zone 'Asia/Seoul')::date),
               max((timestamp at time zone 'Asia/Seoul')::date),
               count(*),
               count(distinct (timestamp at time zone 'Asia/Seoul')::date)
        from intraday_prices
        where stock_code=%s and source=%s and time_frame=%s
        """,
        (stock_code, SOURCE, TIME_FRAME),
    )
    row = cur.fetchone()
    return {"first_day": str(row[0]) if row and row[0] else None, "last_day": str(row[1]) if row and row[1] else None, "rows": int(row[2] or 0), "days": int(row[3] or 0)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--limit-per-date", type=int, default=100)
    parser.add_argument("--json-out", default="reports/fujimoto_126_missing_next_day.json")
    args = parser.parse_args()

    env = read_env(PROJECT_ROOT / ".env")
    if not env.get("DATABASE_URL"):
        print(json.dumps({"ok": False, "blocking_conditions": ["missing_database_url"]}, ensure_ascii=False, indent=2))
        return 2

    import psycopg

    missing: list[dict[str, Any]] = []
    covered: list[dict[str, Any]] = []
    with psycopg.connect(env["DATABASE_URL"], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            for signal_day in fetch_signal_dates(cur, parse_day(args.start_date), parse_day(args.end_date)):
                for sig in fetch_buy_signals(cur, signal_day, args.limit_per_date):
                    code = str(sig["stock_code"])
                    next_day = next_minute_day(cur, code, signal_day)
                    base = {"signal_date": str(signal_day), "stock_code": code, "source_signal_id": sig["id"], "score": float(sig["score"] or 0)}
                    if next_day is None:
                        missing.append({**base, "minute_coverage": minute_coverage(cur, code), "blocking_condition": "next_trading_day_ka10080_minute_missing"})
                    else:
                        covered.append({**base, "next_minute_day": str(next_day)})

    data = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE,
        "time_frame": TIME_FRAME,
        "covered_count": len(covered),
        "missing_count": len(missing),
        "covered": covered,
        "missing": missing,
        "summary": {
            "missing_codes": sorted({row["stock_code"] for row in missing}),
            "covered_codes": sorted({row["stock_code"] for row in covered}),
        },
    }
    out = PROJECT_ROOT / args.json_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    printable = {k: v for k, v in data.items() if k not in {"missing", "covered"}}
    printable["json_out"] = str(out)
    print(json.dumps(printable, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
