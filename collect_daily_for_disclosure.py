#!/usr/bin/env python3
"""
Collect daily OHLCV for a given list of stock codes using Kiwoom ka10081
and upsert into Supabase via REST API.
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from core.supabase_rest import SupabaseRestClient

# Import the Kiwoom functions from the existing script
SCRIPT_DIR = PROJECT_ROOT / 'scripts'
sys.path.insert(0, str(SCRIPT_DIR))
import collect_daily_prices_kiwoom as kc

def main():
    # Stock codes we want: those with disclosures
    stock_codes = ['004410', '008700', '015260']
    # Optional: you can also add more if you wish
    # stock_codes += ['005930']  # for reference

    sb = SupabaseRestClient()
    env = kc.load_env()
    trading_env = kc.get_trading_env(env)
    appkey = kc.env_get(env, "KIWOOM_REST_API_KEY", trading_env)
    secretkey = kc.env_get(env, "KIWOOM_REST_API_SECRET", trading_env)
    if not appkey or not secretkey:
        print("Missing Kiwoom credentials")
        return 1
    host = kc.base_url(trading_env)
    print(f"Fetching token from {host}...")
    token = kc.issue_token(host, appkey, secretkey)
    print("Token acquired.")

    base_dt = datetime.now().strftime('%Y%m%d')
    print(f"Collecting daily data for {len(stock_codes)} stocks up to {base_dt}...")

    total_inserted = 0
    for i, code in enumerate(stock_codes, start=1):
        print(f"[{i}/{len(stock_codes)}] {code} ...", end=' ')
        try:
            raw_rows = kc.call_ka10081(host, token, code, base_dt)
            rows = kc.parse_daily_rows(code, raw_rows)
            if not rows:
                print("SKIP: no rows parsed")
                continue
            # Upsert via Supabase REST
            # We'll use the supabase_rest client's upsert_rows method on daily_prices table
            # Note: the table has a unique constraint on (stock_code, date)
            result = sb.upsert_rows('daily_prices', rows, on_conflict='stock_code,date')
            inserted = len(result)
            total_inserted += inserted
            print(f"OK: {inserted} rows (from {rows[0]['date']} to {rows[-1]['date']})")
        except Exception as e:
            print(f"FAILED: {e}")
        # Be polite to the API
        time.sleep(0.5)

    print(f"\nTotal rows inserted/updated: {total_inserted}")
    # Quick verification
    for code in stock_codes:
        rows = sb.get('daily_prices', params={'stock_code': code})
        print(f"{code}: {len(rows)} rows in DB")
        if rows:
            dates = [r['date'] for r in rows]
            print(f"  Date range: {min(dates)} ~ {max(dates)}")
    return 0

if __name__ == '__main__':
    sys.exit(main())