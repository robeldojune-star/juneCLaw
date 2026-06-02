import sys
sys.path.insert(0, '/home/june/trading')
from core.fujimoto_126_filter import PriceBar, evaluate_fujimoto_126
from datetime import datetime, timezone
import json
from pathlib import Path

# Helper to convert string to PriceBar (simplified)
def bar_from_dict(d, dt):
    return PriceBar(
        ts=dt,
        hhmm=d['hhmm'],
        open=d['open'],
        high=d['high'],
        low=d['low'],
        close=d['close'],
        volume=d['volume']
    )

def load_bars_for_signal(stock_code, trading_day):
    # We'll fetch from the database using the same method as in the chart script
    import os
    from dotenv import load_dotenv
    PROJECT_ROOT = Path(__file__).resolve().parents[0]
    load_dotenv(PROJECT_ROOT / '.env')
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise Exception("DATABASE_URL not set")
    import psycopg
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select timestamp, open, high, low, close, volume
                from intraday_prices
                where stock_code=%s and source=%s and time_frame=%s
                  and (timestamp at time zone 'Asia/Seoul')::date=%s
                order by timestamp asc
                """,
                (stock_code, 'kiwoom_ka10080_minute', '1min', trading_day)
            )
            out = []
            for ts, o, h, l, c, v in cur.fetchall():
                # convert to KST
                from datetime import timedelta
                KST = timezone(timedelta(hours=9))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                dt = ts.astimezone(KST)
                out.append({
                    'timestamp': dt,
                    'hhmm': dt.strftime('%H:%M'),
                    'open': float(o),
                    'high': float(h),
                    'low': float(l),
                    'close': float(c),
                    'volume': int(v or 0)
                })
            return out

def main():
    json_path = Path('/home/june/trading/reports/fujimoto_126_backtest_signals_full.json')
    data = json.loads(json_path.read_text(encoding='utf-8'))
    results = data.get('results', [])
    # Filter to successful ones
    candidates = [r for r in results if r.get('ok') is True]
    # Sort by net return descending
    candidates.sort(key=lambda r: float(r.get('net_return_pct') or -999), reverse=True)
    
    print(f"Found {len(candidates)} successful signals. Checking first 10...")
    for idx, row in enumerate(candidates[:10]):
        stock_code = row.get('stock_code')
        trading_day_str = row.get('entry_trading_date') or row.get('trading_day')
        if not stock_code or not trading_day_str:
            continue
        print(f"\n--- Signal {idx+1}: {stock_code} {trading_day_str} ---")
        try:
            bars = load_bars_for_signal(stock_code, trading_day_str)
        except Exception as e:
            print(f"  Failed to load bars: {e}")
            continue
        if not bars:
            print("  No bars found.")
            continue
        # Convert to PriceBar objects
        price_bars = []
        for b in bars:
            # We need to create a datetime object for ts; we already have timestamp as datetime
            price_bars.append(PriceBar(
                ts=b['timestamp'],
                hhmm=b['hhmm'],
                open=b['open'],
                high=b['high'],
                low=b['low'],
                close=b['close'],
                volume=b['volume']
            ))
        # Find first signal bar
        first_signal_idx = None
        for i in range(len(price_bars)):
            window = price_bars[:i+1]
            res = evaluate_fujimoto_126(window, min_score=60.0)
            if res.get('signal') == 'HIGH_CONFIDENCE_CANDIDATE':
                first_signal_idx = i
                break
        if first_signal_idx is None:
            print("  No signal found in the entire day!")
            continue
        print(f"  First signal at bar index {first_signal_idx} (time {price_bars[first_signal_idx].hhmm})")
        # Check entry: we entered at the close of that bar (as per our simulation)
        entry_price = price_bars[first_signal_idx].close
        print(f"  Entry price (close of signal bar): {entry_price}")
        # Check Ichimoku at that point: we need to compute the Ichimoku series up to that bar
        from core.fujimoto_126_filter import ichimoku_series
        ichimoku = ichimoku_series(price_bars[:first_signal_idx+1])
        span_b = ichimoku.get('span_b')
        # The last value of span_b is what we would have used at that bar
        last_span_b = span_b[-1] if span_b else None
        print(f"  Ichimoku span_b at signal bar: {last_span_b}")
        if last_span_b is None:
            print("  WARNING: Ichimoku span_b is None (insufficient bars for calculation)!")
        # Check if the signal bar is a doji with long upper shadow
        bar = price_bars[first_signal_idx]
        open_price = bar.open
        close_price = bar.close
        high_price = bar.high
        low_price = bar.low
        body = abs(close_price - open_price)
        total_range = high_price - low_price
        # Doji: body very small relative to range
        is_doji = body < 0.1 * total_range if total_range > 0 else False
        # Long upper shadow: (high - max(open, close)) > 2 * body? or something
        upper_shadow = high_price - max(open_price, close_price)
        is_long_upper = upper_shadow > 2 * body if body > 0 else False
        print(f"  Bar details: O={open_price}, H={high_price}, L={low_price}, C={close_price}")
        print(f"  Body={body:.2f}, Range={total_range:.2f}, Upper shadow={upper_shadow:.2f}")
        print(f"  Is doji? {is_doji} (body < 10% of range)")
        print(f"  Is long upper shadow? {is_long_upper} (upper shadow > 2*body)")
        if is_doji and is_long_upper:
            print("  NOTE: This bar is a doji with long upper shadow.")
        # Also, we can check if we had any prior signals that were ignored? Not needed.
    print("\nDone.")

if __name__ == '__main__':
    main()