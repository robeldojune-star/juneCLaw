#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from core.fujimoto_126_filter import PriceBar, evaluate_fujimoto_126
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
sb = SupabaseRestClient()
def fetch_bars(stock, date):
    rows = sb.get('intraday_prices', {'stock_code': f'eq.{stock}', 'source': f'eq.kiwoom_ka10080_minute', 'time_frame': f'eq.1min', 'timestamp': f'gte.{date.isoformat()}', 'timestamp': f'lt.{(date+timedelta(days=1)).isoformat()}'}, timeout=10)
    bars = []
    for r in rows:
        dt = datetime.fromisoformat(r['timestamp'])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(KST)
        bars.append(PriceBar(ts=dt, hhmm=dt.strftime('%H:%M'), open=float(r['open']), high=float(r['high']), low=float(r['low']), close=float(r['close']), volume=int(r['volume'] or 0)))
    bars.sort(key=lambda b: b.ts)
    return bars

# test one stock, one day
stock = '005930'
today = datetime.now(KST).date()
yesterday = today - timedelta(days=1)
bars = fetch_bars(stock, yesterday)
print(f'Bars fetched: {len(bars)}')
if bars:
    ev = evaluate_fujimoto_126(bars, min_score=0)
    print(f'Signal: {ev.get("signal")}, Score: {ev.get("score_total")}')
else:
    print('No bars')