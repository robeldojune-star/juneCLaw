#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from core.fujimoto_126_filter import PriceBar, evaluate_fujimoto_126
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
    stock_codes = ['005930', '000660']
    # Use last 3 days with data (we saw from earlier)
    target_dates = [datetime(2026,5,27, tzinfo=KST).date(),
                    datetime(2026,5,28, tzinfo=KST).date(),
                    datetime(2026,5,29, tzinfo=KST).date()]
    for sc in stock_codes:
        print(f"\n=== {sc} ===")
        all_bars = fetch_all_bars_for_stock(sb, sc)
        grouped = {}
        for bar in all_bars:
            d = bar.ts.date()
            if d not in grouped:
                grouped[d] = []
            grouped[d].append(bar)
        for date in target_dates:
            bars = grouped.get(date, [])
            if not bars:
                print(f"  {date}: no bars")
                continue
            print(f"  {date}: {len(bars)} bars")
            # Evaluate with default min_score=60, include_order_blocks=False to see internal score
            result = evaluate_fujimoto_126(bars, min_score=60, include_order_blocks=False)
            print(f"    signal: {result['signal']}")
            print(f"    score_total: {result['score_total']}")
            print(f"    blocking_conditions: {result['blocking_conditions']}")
            # Also compute RSI manually for last bar
            closes = [b.close for b in bars if b.close is not None]
            # simple RSI calculation for last value
            if len(closes) >= 15:
                gains = []
                losses = []
                for i in range(1,15):
                    change = closes[i] - closes[i-1]
                    if change >=0:
                        gains.append(change)
                        losses.append(0.0)
                    else:
                        gains.append(0.0)
                        losses.append(-change)
                avg_gain = sum(gains)/14
                avg_loss = sum(losses)/14
                if avg_loss == 0:
                    rsi = 100.0
                else:
                    rs = avg_gain/avg_loss
                    rsi = 100.0 - (100.0/(1.0+rs))
                # update with remaining
                for i in range(15, len(closes)):
                    change = closes[i] - closes[i-1]
                    gain = max(change,0.0)
                    loss = max(-change,0.0)
                    avg_gain = (avg_gain*13 + gain)/14
                    avg_loss = (avg_loss*13 + loss)/14
                    if avg_loss == 0:
                        rsi = 100.0
                    else:
                        rs = avg_gain/avg_loss
                        rsi = 100.0 - (100.0/(1.0+rs))
                print(f"    last close: {closes[-1]}, RSI(14): {rsi:.2f}")
            else:
                print(f"    not enough closes for RSI")
            # Try with min_score=50 and see if signal changes
            result2 = evaluate_fujimoto_126(bars, min_score=50, include_order_blocks=False)
            print(f"    min_score=50 -> signal: {result2['signal']}, score: {result2['score_total']}")

if __name__ == '__main__':
    main()