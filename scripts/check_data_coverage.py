#!/usr/bin/env python3
"""
Check the state of data: which stocks have disclosures, which have daily prices, and which are active.
"""

import os
import sys
from collections import defaultdict

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

from core.supabase_rest import SupabaseRestClient

def main():
    sb = SupabaseRestClient()
    
    print("=== Disclosures ===")
    disclosures = sb.get('dart_disclosures')
    print(f"Total disclosure rows: {len(disclosures)}")
    disclosure_stocks = set(d['stock_code'] for d in disclosures)
    print(f"Unique stocks with disclosures: {len(disclosure_stocks)}")
    print(f"Stocks: {sorted(disclosure_stocks)}")
    
    print("\n=== Daily Prices ===")
    daily_prices = sb.get('daily_prices')
    print(f"Total daily price rows: {len(daily_prices)}")
    daily_stocks = set(d['stock_code'] for d in daily_prices)
    print(f"Unique stocks with daily prices: {len(daily_stocks)}")
    print(f"Stocks: {sorted(daily_stocks)}")
    
    print("\n=== KOSPI Top 50 (active) ===")
    kospi = sb.get('kospi_top50', params={'is_active': 'eq.True'})
    print(f"Total active KOSPI stocks: {len(kospi)}")
    kospi_stocks = set(k['stock_code'] for k in kospi)
    print(f"Unique active stocks: {len(kospi_stocks)}")
    print(f"Stocks: {sorted(kospi_stocks)}")
    
    # Intersections
    print("\n=== Intersections ===")
    print(f"Disclosure ∩ Daily Prices: {len(disclosure_stocks & daily_stocks)}")
    if disclosure_stocks & daily_stocks:
        print(f"  Stocks: {sorted(disclosure_stocks & daily_stocks)}")
    else:
        print("  None")
    
    print(f"Disclosure ∩ Active KOSPI: {len(disclosure_stocks & kospi_stocks)}")
    if disclosure_stocks & kospi_stocks:
        print(f"  Stocks: {sorted(disclosure_stocks & kospi_stocks)}")
    else:
        print("  None")
    
    print(f"Daily Prices ∩ Active KOSPI: {len(daily_stocks & kospi_stocks)}")
    if daily_stocks & kospi_stocks:
        print(f"  Stocks: {sorted(daily_stocks & kospi_stocks)}")
    else:
        print("  None")
    
    # Check if there are any disclosures for the stocks that have daily prices
    print("\n=== Checking for missing data ===")
    # For each stock in daily_stocks, see if we have disclosures
    for stock in sorted(daily_stocks):
        if stock in disclosure_stocks:
            print(f"✓ {stock}: has disclosures")
        else:
            print(f"✗ {stock}: NO disclosures")
    # For each stock in disclosure_stocks, see if we have daily prices
    for stock in sorted(disclosure_stocks):
        if stock in daily_stocks:
            print(f"✓ {stock}: has daily prices")
        else:
            print(f"✗ {stock}: NO daily prices")
    
    # Let's also check the date ranges for daily prices for a few stocks
    print("\n=== Date ranges for daily prices (sample) ===")
    for stock in sorted(list(daily_stocks)[:5]):
        rows = [d for d in daily_prices if d['stock_code'] == stock]
        if rows:
            dates = [d['date'] for d in rows]
            print(f"{stock}: {len(rows)} rows, from {min(dates)} to {max(dates)}")
        else:
            print(f"{stock}: no rows")
    
    # And for disclosures date range
    print("\n=== Date ranges for disclosures (sample) ===")
    for stock in sorted(list(disclosure_stocks)[:5]):
        rows = [d for d in disclosures if d['stock_code'] == stock]
        if rows:
            dates = [d['rcept_dt'] for d in rows]
            print(f"{stock}: {len(rows)} disclosures, from {min(dates)} to {max(dates)}")
        else:
            print(f"{stock}: no disclosures")

if __name__ == '__main__':
    main()