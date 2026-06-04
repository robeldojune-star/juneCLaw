#!/usr/bin/env python3
"""Collect daily OHLCV via Kiwoom ka10081 into Supabase daily_prices table.

Read-only. No orders. Upserts so re-runs are safe.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import sys
import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.kiwoom_client import KiwoomAPIClient
from core.market_data_service import MarketDataService, normalize_stock_code, is_stock_code
from core.supabase_rest import SupabaseRestClient

KST = ZoneInfo("Asia/Seoul")
TABLE = "daily_prices"

STOCKS_TOP20 = [
    "005930", "000660", "035420", "005380", "068270",
    "009150", "373220", "402340", "207940", "042660",
    "005490", "012330", "035720", "051910", "000270",
    "006400", "028260", "086790", "105560", "055550",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect daily OHLCV via ka10081")
    p.add_argument("--stock-codes", nargs="+", default=STOCKS_TOP20)
    p.add_argument("--days", type=int, default=90, help="Days of history to fetch")
    p.add_argument("--delay", type=float, default=0.3, help="Delay between stocks (seconds)")
    p.add_argument("--trading-env", choices=["mock", "prod"], default="prod")
    return p.parse_args()


def upsert_batch(sb: SupabaseRestClient, rows: list[dict[str, Any]]) -> int:
    """Upsert rows into daily_prices. Returns count inserted."""
    if not rows:
        return 0
    try:
        resp = sb.upsert_rows(TABLE, rows, on_conflict="stock_code,date")
        return len(rows)
    except Exception as e:
        print(f"  upsert error: {e}")
        # Fall back to individual inserts
        count = 0
        for row in rows:
            try:
                sb.upsert_rows(TABLE, [row], on_conflict="stock_code,date")
                count += 1
            except Exception:
                pass
        return count


def main() -> None:
    args = parse_args()
    env_path = PROJECT_ROOT / "envs" / args.trading_env / ".env"
    client = KiwoomAPIClient.from_env(env_path=env_path)
    mkt = MarketDataService(client)
    sb = SupabaseRestClient()

    token = client.issue_token(force=True)
    if not token:
        print("OAuth token issue failed")
        return

    now_kst = datetime.now(KST)
    base_dt = now_kst.strftime("%Y%m%d")

    total_upserted = 0
    results = []

    for stock in args.stock_codes:
        print(f"\n=== {stock} ===")
        try:
            rows = mkt.get_daily_chart_raw(stock, base_dt=base_dt, adjusted_price=True)
        except Exception as e:
            print(f"  API error: {e}")
            results.append({"stock": stock, "status": "api_error", "error": str(e)})
            time.sleep(args.delay)
            continue

        if not rows:
            print(f"  no data")
            results.append({"stock": stock, "status": "empty"})
            time.sleep(args.delay)
            continue

        # Parse and filter
        parsed = []
        code = normalize_stock_code(stock)
        cutoff = (now_kst - timedelta(days=args.days)).strftime("%Y%m%d")

        for row in rows:
            if not isinstance(row, dict):
                continue
            dt = str(row.get("dt") or "").strip()
            if not dt.isdigit() or len(dt) != 8:
                continue
            if dt < cutoff:
                continue

            try:
                parsed.append({
                    "stock_code": code,
                    "date": f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}",
                    "open": abs(int(row.get("open_pric", 0) or 0)),
                    "high": abs(int(row.get("high_pric", 0) or 0)),
                    "low": abs(int(row.get("low_pric", 0) or 0)),
                    "close": abs(int(row.get("cur_prc", 0) or 0)),
                    "volume": abs(int(row.get("trde_qty", 0) or 0)),
                    "source": "kiwoom_ka10081_daily",
                })
            except (ValueError, TypeError):
                continue

        if parsed:
            count = upsert_batch(sb, parsed)
            total_upserted += count
            dates = sorted(set(r["date"] for r in parsed))
            print(f"  upserted {count} rows, {dates[0]} ~ {dates[-1]}")
            results.append({"stock": stock, "status": "ok", "rows": count, "date_range": f"{dates[0]}~{dates[-1]}"})
        else:
            print(f"  no valid rows after filter")
            results.append({"stock": stock, "status": "no_valid_rows"})

        time.sleep(args.delay)

    print(f"\n=== Done: {total_upserted} total rows upserted across {len(args.stock_codes)} stocks ===")
    print(json.dumps({"total_upserted": total_upserted, "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
