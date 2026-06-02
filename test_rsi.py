#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))

sb = SupabaseRestClient()
def fetch_bars_kst_date(stock, kst_date):
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

def compute_rsi(closes, period=14):
    if len(closes) < period:
        return [None] * len(closes)
    rsi = [None] * (period - 1)
    gains = []
    losses = []
    for i in range(1, period):
        change = closes[i] - closes[i-1]
        if change >= 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-change)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        rsi.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi.append(100.0 - (100.0 / (1.0 + rs)))
    for i in range(period, len(closes)):
        change = closes[i] - closes[i-1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rsi_val = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_val = 100.0 - (100.0 / (1.0 + rs))
        rsi.append(rsi_val)
    return rsi

# test
stock = '005930'
date = datetime(2026, 5, 31).date()
bars = fetch_bars_kst_date(stock, date)
print(f'Fetched {len(bars)} bars')
if bars:
    closes = [b['close'] for b in bars]
    rsi = compute_rsi(closes, 14)
    # find first non-None
    first_valid = next((i for i, v in enumerate(rsi) if v is not None), None)
    if first_valid is not None:
        print(f'First RSI at index {first_valid}: {rsi[first_valid]}')
        print(f'Last RSI: {rsi[-1]}')
        # count how many below 30
        below30 = sum(1 for v in rsi if v is not None and v < 30)
        above70 = sum(1 for v in rsi if v is not None and v > 70)
        print(f'RSI <30: {below30}, >70: {above70}')
    else:
        print('No RSI values')
else:
    print('No bars')