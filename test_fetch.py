#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
sb = SupabaseRestClient()
# Test one stock, one day
stock_code = "005930"
end_date = datetime.now(KST).date()
start_date = end_date - timedelta(days=2)
print(f"Testing {stock_code} from {start_date} to {end_date}")
current = start_date
while current <= end_date:
    print(f"Fetching {current}...")
    rows = sb.get('intraday_prices', {
        'stock_code': f'eq.{stock_code}',
        'source': f'eq.kiwoom_ka10080_minute',
        'time_frame': f'eq.1min'
    }, timeout=10)
    print(f"  Got {len(rows)} rows")
    # Filter by date
    from core.fujimoto_126_filter import PriceBar
    bars = []
    for row in rows:
        ts = row['timestamp']
        # parse
        if isinstance(ts, str):
            if ts.endswith('Z'):
                ts = ts[:-1] + '+00:00'
            dt = datetime.fromisoformat(ts)
        else:
            dt = ts
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(KST)
        if dt.date() == current:
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
    print(f"  Bars for {current}: {len(bars)}")
    current += timedelta(days=1)
print("Done")