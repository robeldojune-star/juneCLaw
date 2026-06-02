#!/usr/bin/env python3
"""
Collect OpenDART disclosures for active KOSPI stocks and store in Supabase.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

# Ensure the OpenDART module gets the API key via DART_API_KEY env var
dart_key = os.getenv('OPENDART_API_KEY')
if dart_key:
    os.environ['DART_API_KEY'] = dart_key
else:
    print("Error: OPENDART_API_KEY not found in .env")
    sys.exit(1)

from core.supabase_rest import SupabaseRestClient

# Import OpenDART functions from the skill
SKILL_SCRIPTS = PROJECT_ROOT / '.hermes' / 'skills' / '.openclaw' / 'skills' / 'opendart-api' / 'scripts'
sys.path.insert(0, str(SKILL_SCRIPTS))

# Now import the modules
import get_disclosures as dart_disclosures
import get_corp_code as dart_corp

def main():
    # Initialize Supabase client
    sb = SupabaseRestClient()
    
    # Get active KOSPI stocks
    print("Fetching active KOSPI stocks...")
    params = {'is_active': 'eq.True', 'select': 'stock_code,stock_name'}
    stocks = sb.get('kospi_top50', params=params)
    print(f"Found {len(stocks)} active stocks.")
    
    # For testing, only take the first 5 stocks
    stocks = stocks[:5]
    print(f"Testing with first {len(stocks)} stocks.")
    
    # Date range: last 180 days
    end_de = datetime.now().strftime('%Y%m%d')
    bgn_de = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d')
    print(f"Fetching disclosures from {bgn_de} to {end_de}")
    
    total_inserted = 0
    total_skipped = 0
    
    for i, stock in enumerate(stocks, 1):
        stock_code = stock['stock_code']
        stock_name = stock['stock_name']
        print(f"[{i}/{len(stocks)}] Processing {stock_code} ({stock_name})...", end=' ')
        
        # Get corp_code
        corp_code = dart_corp.get_corp_code(stock_code)
        if not corp_code:
            print("SKIP: corp_code not found")
            total_skipped += 1
            continue
        
        # Fetch disclosures
        disclosures = dart_disclosures.get_disclosures(corp_code, days=180)
        if not disclosures:
            print("NO DISCLOSURES")
            continue
        
        print(f"FOUND {len(disclosures)} disclosures")
        
        # Prepare rows for insertion
        rows = []
        for d in disclosures:
            rows.append({
                'corp_code': d['corp_code'],
                'stock_code': d['stock_code'],
                'rcept_no': d['rcept_no'],
                'rcept_dt': d['rcept_dt'],
                'report_nm': d['report_nm'],
                'flr_nm': d['flr_nm'],
                'url': f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={d['rcept_no']}"
            })
        
        # Upsert rows (ignore duplicates on rcept_no)
        if rows:
            try:
                result = sb.upsert_rows('dart_disclosures', rows, on_conflict='rcept_no')
                inserted = len(result)
                total_inserted += inserted
                print(f"  -> Inserted {inserted} new rows")
            except Exception as e:
                print(f"  -> Error inserting rows: {e}")
        
        # Be polite to the API: delay between requests
        time.sleep(0.1)
    
    print("\n=== Summary ===")
    print(f"Total stocks processed: {len(stocks)}")
    print(f"Total new disclosures inserted: {total_inserted}")
    print(f"Stocks skipped (no corp_code): {total_skipped}")

if __name__ == '__main__':
    main()