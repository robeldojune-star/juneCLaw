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
    print(f"Fetched {len(rows)} raw rows for {stock_code}")
    if rows:
        print("First row:", rows[0])
        print("Last row:", rows[-1])
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
        print(f"Total bars: {len(bars)}")
        print(f"First bar: {bars[0]}")
        print(f"Last bar: {bars[-1]}")
        # count per date
        from collections import Counter
        dates = [b['date'] for b in bars]
        cnt = Counter(dates)
        print("Bars per date:", dict(cnt))
        # show a few bars around market open
        for b in bars[:5]:
            print(f"  {b['date']} {b['time']} close={b['close']}")

if __name__ == '__main__':
    main()