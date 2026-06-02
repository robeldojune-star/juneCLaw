#!/usr/bin/env python3
"""Check signal generation for a few stocks and dates."""
import sys
import json
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from core.fujimoto_126_filter import PriceBar, evaluate_fujimoto_126

KST = timezone(timedelta(hours=9))
SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"

def load_kospi_top50(csv_path='/home/june/trading/data/kospi_top50_common_stocks_marketcap_naver.csv'):
    codes = []
    try:
        with open(csv_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get('종목코드')
                if code:
                    codes.append(code.strip())
    except Exception as e:
        print(f"Failed to load KOSPI Top 50 list: {e}")
        codes = []
    seen = set()
    deduped = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped

KOSPI_TOP_50 = load_kospi_top50()
print(f"Loaded {len(KOSPI_TOP_50)} stocks.")

def ts_to_kst(value):
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)

def fetch_all_bars_for_stock(sb, stock_code):
    rows = sb.get('intraday_prices', {
        'stock_code': f'eq.{stock_code}',
        'source': f'eq.{SOURCE}',
        'time_frame': f'eq.{TIME_FRAME}'
    }, timeout=20)
    bars = []
    for row in rows:
        ts = row['timestamp']
        dt = ts_to_kst(ts)
        bars.append(PriceBar(
            ts=dt,
            hhmm=dt.strftime('%H:%M'),
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=int(row['volume'] or 0)
        ))
    bars.sort(key=lambda b: b.ts)
    return bars

def main():
    sb = SupabaseRestClient()
    # test a few stocks and recent dates
    test_stocks = ["005930", "000660", "307950"]  # Samsung, SK Hynix, Hyundai AutoEver
    end_date = datetime.now(KST).date()
    start_date = end_date - timedelta(days=5)
    print(f"Checking signals from {start_date} to {end_date}")
    for stock in test_stocks:
        print(f"\n=== {stock} ===")
        all_bars = fetch_all_bars_for_stock(sb, stock)
        bars_by_date = defaultdict(list)
        for bar in all_bars:
            bars_by_date[bar.ts.date()].append(bar)
        current = start_date
        while current <= end_date:
            bars = bars_by_date.get(current, [])
            if not bars:
                current += timedelta(days=1)
                continue
            # evaluate signal using all bars up to each time? Let's just evaluate on whole day bars
            window = bars  # using all intraday bars of the day
            eval_result = evaluate_fujimoto_126(window, min_score=0)  # low threshold to see score
            signal = eval_result.get("signal", "")
            score = eval_result.get("score", 0)
            details = eval_result.get("details", {})
            print(f"  {current}: bars={len(bars)}, signal={signal}, score={score:.2f}")
            if details:
                # print a few key components
                key_items = [k for k in details.keys() if not k.startswith('_')][:5]
                if key_items:
                    print(f"    details: {', '.join(f'{k}:{details[k]:.2f}' for k in key_items)}")
            current += timedelta(days=1)

if __name__ == '__main__':
    main()