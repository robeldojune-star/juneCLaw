"""Remove intraday_prices rows that were inserted before ka10005 minute semantics were validated.

This only targets rows created from source=kiwoom_ka10005, time_frame=1min, whose
stored timestamp is exactly the synthetic 15:30 bucket. It does not delete any
future rows with explicit intraday times.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import read_env  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually delete rows; default is dry-run")
    args = parser.parse_args()

    try:
        import psycopg
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "status": "blocked", "blocking_conditions": ["missing_psycopg"], "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        return 2

    env = read_env(PROJECT_ROOT / ".env")
    dsn = env.get("DATABASE_URL")
    if not dsn:
        print(json.dumps({"ok": False, "status": "blocked", "blocking_conditions": ["missing_database_url"]}, ensure_ascii=False, indent=2))
        return 2

    where_sql = "source = 'kiwoom_ka10005' and time_frame = '1min' and ((timestamp at time zone 'Asia/Seoul')::time = time '15:30:00')"
    with psycopg.connect(dsn, connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(f"select count(*) from intraday_prices where {where_sql}")
            count = int(cur.fetchone()[0])
            sample = []
            if count:
                cur.execute(
                    f"select stock_code, timestamp::text, time_frame, source from intraday_prices where {where_sql} order by timestamp desc limit 10"
                )
                sample = [
                    {"stock_code": r[0], "timestamp": r[1], "time_frame": r[2], "source": r[3]}
                    for r in cur.fetchall()
                ]
            deleted = 0
            if args.apply and count:
                cur.execute(f"delete from intraday_prices where {where_sql}")
                deleted = cur.rowcount or 0
        if args.apply:
            conn.commit()
        else:
            conn.rollback()

    out = {
        "ok": True,
        "stage": "cleanup_unvalidated_intraday_rows",
        "mode": "apply" if args.apply else "dry_run",
        "matched_rows": count,
        "deleted_rows": deleted,
        "sample": sample,
        "blocking_conditions": [],
        "alerts": ["deletes only synthetic_1530_bucket rows from source=kiwoom_ka10005/time_frame=1min"],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
