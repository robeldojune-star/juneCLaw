import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from core.fujimoto_126_filter import PriceBar, evaluate_fujimoto_126, simulate_fujimoto_126_trade
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

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

def parse_day(text):
    return datetime.fromisoformat(text[:10]).date()

def fetch_bars_for_day(sb, stock_code, trading_day):
    # Fetch all rows for the stock, source, time_frame (no date filter) then filter by date in KST
    # This is okay because we expect only a few days of data per stock.
    rows = sb.get('intraday_prices', {
        'stock_code': f'eq.{stock_code}',
        'source': f'eq.{SOURCE}',
        'time_frame': f'eq.{TIME_FRAME}'
    }, timeout=30)
    bars = []
    for row in rows:
        ts = row['timestamp']
        dt = ts_to_kst(ts)
        if dt.date() == trading_day:
            bars.append(PriceBar(
                ts=dt,
                hhmm=dt.strftime('%H:%M'),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=int(row['volume'] or 0)
            ))
    # Sort by time
    bars.sort(key=lambda b: b.ts)
    return bars

def is_doji_long_upper(bar):
    open_price = bar.open
    close_price = bar.close
    high_price = bar.high
    low_price = bar.low
    if high_price == low_price:
        return False
    body = abs(close_price - open_price)
    total_range = high_price - low_price
    is_doji = body < 0.1 * total_range if total_range > 0 else False
    upper_shadow = high_price - max(open_price, close_price)
    is_long_upper = upper_shadow > 2 * body if body > 0 else False
    return is_doji, is_long_upper, body, total_range, upper_shadow

def main():
    sb = SupabaseRestClient()
    json_path = Path('/home/june/trading/reports/fujimoto_126_backtest_signals_full.json')
    data = json.loads(json_path.read_text(encoding='utf-8'))
    results = data.get('results', [])
    signals = [r for r in results if r.get('ok') is True]
    print(f"Found {len(signals)} successful signals.")
    all_ok = True
    for sig in signals:
        stock_code = sig.get('stock_code')
        entry_date_str = sig.get('entry_trading_date')
        signal_date_str = sig.get('signal_date')
        entry_time = sig.get('entry_time')
        entry_price = sig.get('entry_price')
        exit_reason = sig.get('exit_reason')
        net_return = sig.get('net_return_pct')
        if not stock_code or not entry_date_str:
            print(f"Skipping signal due to missing fields: {sig}")
            continue
        entry_date = parse_day(entry_date_str)
        print(f"\n=== Checking {stock_code} on {entry_date} (signal date {signal_date_str}) ===")
        bars = fetch_bars_for_day(sb, stock_code, entry_date)
        if not bars:
            print(f"  ERROR: No bars found for {stock_code} on {entry_date}")
            all_ok = False
            continue
        print(f"  Loaded {len(bars)} 1-minute bars.")
        # Find first signal bar
        first_signal_idx = None
        for i in range(len(bars)):
            window = bars[:i+1]
            res = evaluate_fujimoto_126(window, min_score=60.0)
            if res.get('signal') == 'HIGH_CONFIDENCE_CANDIDATE':
                first_signal_idx = i
                break
        if first_signal_idx is None:
            print(f"  ERROR: No HIGH_CONFIDENCE_CANDIDATE signal found in the day!")
            all_ok = False
            continue
        print(f"  First signal at bar index {first_signal_idx} (time {bars[first_signal_idx].hhmm})")
        # Check that the signal bar matches the entry time from JSON (should be same)
        if bars[first_signal_idx].hhmm != entry_time:
            print(f"  WARNING: Signal bar time {bars[first_signal_idx].hhmm} differs from JSON entry_time {entry_time}")
        # Check entry price matches close of that bar (within rounding)
        bar_close = bars[first_signal_idx].close
        if abs(bar_close - entry_price) > 0.01:  # allow small difference due to rounding?
            print(f"  WARNING: Entry price from JSON {entry_price} differs from bar close {bar_close}")
        # Check Ichimoku availability: need at least 52 bars up to and including this bar
        if first_signal_idx < 51:
            print(f"  ERROR: Ichimoku span_b not available (need at least 52 bars, have {first_signal_idx+1})")
            all_ok = False
        else:
            print(f"  Ichimoku span_b available (bars count = {first_signal_idx+1} >= 52)")
        # Check doji/long upper shadow
        bar = bars[first_signal_idx]
        is_doji, is_long_upper, body, total_range, upper_shadow = is_doji_long_upper(bar)
        if is_doji and is_long_upper:
            print(f"  NOTE: Signal bar is a doji with long upper shadow.")
            print(f"    Body={body:.2f}, Range={total_range:.2f}, Upper shadow={upper_shadow:.2f}")
        else:
            print(f"  Signal bar is NOT a doji with long upper shadow (doji={is_doji}, long upper={is_long_upper})")
            print(f"    Body={body:.2f}, Range={total_range:.2f}, Upper shadow={upper_shadow:.2f}")
        # Simulate trade using the original simulate_fujimoto_126_trade (which uses first signal and simple exit)
        trade = simulate_fujimoto_126_trade(
            bars,
            min_score=60.0,
            stop_loss_pct=-2.0,
            take_profit_pct=3.0,
            time_exit="15:20",
            fee_bps=23.0,
            slippage_bps=10.0
        )
        print(f"  Simulated trade: ok={trade.get('ok')}, exit_reason={trade.get('exit_reason')}, net_return={trade.get('net_return_pct')}")
        if not trade.get('ok'):
            print(f"    Blocking conditions: {trade.get('blocking_conditions')}")
        # Compare with JSON results (should match approximately)
        if trade.get('ok'):
            # Compare net return within 0.01% due to rounding
            if abs(trade.get('net_return_pct', 0) - net_return) > 0.01:
                print(f"    WARNING: Net return mismatch: simulated {trade.get('net_return_pct')} vs JSON {net_return}")
            # Compare exit reason
            if trade.get('exit_reason') != exit_reason:
                print(f"    WARNING: Exit reason mismatch: simulated {trade.get('exit_reason')} vs JSON {exit_reason}")
        else:
            print(f"    Simulated trade failed while JSON marked ok.")
    print("\n=== Summary ===")
    if all_ok:
        print("All signals passed basic checks (Ichimoku available, no doji/long upper shadow unless noted).")
    else:
        print("Some signals had issues.")
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())