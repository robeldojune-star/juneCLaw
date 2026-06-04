#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"

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
    }, timeout=30)
    bars = []
    for row in rows:
        ts = row['timestamp']
        dt = ts_to_kst(ts)
        bars.append({
            'ts': dt,
            'date': dt.date(),
            'time': dt.strftime('%H:%M'),
            'close': float(row['close']) if row['close'] is not None else None
        })
    bars.sort(key=lambda b: b['ts'])
    return bars

def main():
    sb = SupabaseRestClient()
    for sc in ['005930', '000660']:
        print(f"\n=== {sc} ===")
        bars = fetch_all_bars_for_stock(sb, sc)
        if not bars:
            print("No bars")
            continue
        dates = sorted(set(b['date'] for b in bars))
        print(f"Available dates: {dates}")
        print(f"Number of days: {len(dates)}")
        if dates:
            print(f"Earliest: {dates[0]}, Latest: {dates[-1]}")
            # Show the last 3 days
            last_three = dates[-3:] if len(dates) >= 3 else dates
            print(f"Last 3 days: {last_three}")

if __name__ == '__main__':
    main()