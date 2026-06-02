#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
sb = SupabaseRestClient()
def fetch_bars_kst_date(stock, kst_date):
    # kst_date is a datetime.date
    start_kst = datetime.combine(kst_date, datetime.min.time())
    end_kst = start_kst + timedelta(days=1)
    start_utc = start_kst - timedelta(hours=9)
    end_utc = end_kst - timedelta(hours=9)
    start_str = start_utc.isoformat()
    end_str = end_utc.isoformat()
    rows = sb.get('intraday_prices', {
        'stock_code': f'eq.{stock}',
        'source': f'eq.kiwoom_ka10080_minute',
        'time_frame': f'eq.1min',
        'timestamp': f'gte.{start_str}',
        'timestamp': f'lt.{end_str}'
    }, timeout=10)
    bars = []
    for r in rows:
        dt = datetime.fromisoformat(r['timestamp'])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(KST)
        bars.append({
            'ts': dt,
            'hhmm': dt.strftime('%H:%M'),
            'open': float(r['open']),
            'high': float(r['high']),
            'low': float(r['low']),
            'close': float(r['close']),
            'volume': int(r['volume'] or 0)
        })
    bars.sort(key=lambda x: x['ts'])
    return bars

# test for 2026-05-31 KST
kst_date = datetime(2026, 5, 31).date()
bars = fetch_bars_kst_date('005930', kst_date)
print(f'Fetched {len(bars)} bars for 005930 on {kst_date} KST')
if bars:
    print('First bar:', bars[0])
    print('Last bar:', bars[-1])
    # Check if any bars are within market hours 09:00-15:30 KST
    market_bars = [b for b in bars if '09:00' <= b['hhmm'] <= '15:30']
    print(f'Market hour bars: {len(market_bars)}')
else:
    print('No bars')