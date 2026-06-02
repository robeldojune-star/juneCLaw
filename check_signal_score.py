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

stock = '005930'
end_date = datetime.now(KST).date()
start_date = end_date - timedelta(days=4)  # last 5 days
dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
max_score = 0
best_day = None
for d in dates:
    bars = fetch_bars_kst_date(stock, d)
    if not bars:
        continue
    ev = evaluate_fujimoto_126(bars, min_score=0)
    score = ev.get('score_total', 0)
    if score > max_score:
        max_score = score
        best_day = d
    print(f"{d}: score={score}, signal={ev.get('signal')}")
print(f"\nMax score over period: {max_score} on {best_day}")