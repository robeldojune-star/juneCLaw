#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from core.fujimoto_126_filter import PriceBar, evaluate_fujimoto_126
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
        bars.append(PriceBar(
            ts=dt,
            hhmm=dt.strftime('%H:%M'),
            open=float(r['open']),
            high=float(r['high']),
            low=float(r['low']),
            close=float(r['close']),
            volume=int(r['volume'] or 0)
        ))
    bars.sort(key=lambda b: b.ts)
    return bars

# test one stock, one day, with min_score 0
stock = '005930'
date = datetime(2026, 5, 31).date()
bars = fetch_bars_kst_date(stock, date)
print(f'Bars: {len(bars)}')
if bars:
    ev = evaluate_fujimoto_126(bars, min_score=0)
    print(f'Signal: {ev.get("signal")}, Score: {ev.get("score_total")}')
    # also compute SMA 20
    closes = [float(b.close) for b in bars if b.close is not None]
    if len(closes) >= 20:
        sma20 = sum(closes[-20:])/20
        print(f'Last close: {closes[-1]}, SMA20: {sma20}')
    else:
        print('Not enough closes for SMA20')
else:
    print('No bars')