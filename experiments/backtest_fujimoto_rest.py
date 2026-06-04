import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from core.fujimoto_126_filter import PriceBar, simulate_fujimoto_126_trade
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
    # trading_day is a date object
    start_dt = datetime.combine(trading_day, datetime.min.time())
    end_dt = start_dt + timedelta(days=1)
    # Convert to UTC for querying? The timestamp in DB is stored with timezone? We'll use the timestamp column as is.
    # We'll filter by timestamp >= start_dt and timestamp < end_dt, but we need to consider the timezone.
    # Since the data is stored in UTC? Let's look at the example: timestamp: '2026-05-29T06:30:00+00:00' which is UTC.
    # KST is UTC+9, so 09:00 KST = 00:00 UTC.
    # So to get the trading day in KST, we need to query for UTC timestamps between (trading_day at 00:00 KST) and (next day at 00:00 KST).
    # That is: start_utc = datetime.combine(trading_day, datetime.min.time()) - timedelta(hours=9)
    # end_utc = start_utc + timedelta(days=1)
    start_utc = datetime.combine(trading_day, datetime.min.time()) - timedelta(hours=9)
    end_utc = start_utc + timedelta(days=1)
    # Format as ISO strings
    start_str = start_utc.isoformat()
    end_str = end_utc.isoformat()
    params = {
        'stock_code': f'eq.{stock_code}',
        'source': f'eq.{SOURCE}',
        'time_frame': f'eq.{TIME_FRAME}',
        'timestamp': f'gte.{start_str}',
        'timestamp_lt': f'lt.{end_str}'
    }
    # Note: the RestClient get method only accepts equality and maybe other filters? We'll need to check.
    # Looking at the RestClient.get, it builds a query string from params dict, each param is equality.
    # So we cannot use gte and lt directly. We need to use the PostgreSQL range functions? Or we can fetch all and filter in memory.
    # Given the data size per day is about 390 rows, we can fetch all for the stock and source and time_frame and then filter by timestamp.
    # Let's do that: fetch all rows for the stock, source, time_frame, then filter by timestamp in Python.
    # However, if there are many days, this could be heavy. But we are only doing a few days.
    # We'll fetch without date filter, then filter.
    rows = sb.get('intraday_prices', {
        'stock_code': f'eq.{stock_code}',
        'source': f'eq.{SOURCE}',
        'time_frame': f'eq.{TIME_FRAME}'
    }, timeout=30)
    # Filter by timestamp
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

def main():
    sb = SupabaseRestClient()
    # Load the signal JSON
    json_path = Path('/home/june/trading/reports/fujimoto_126_backtest_signals_full.json')
    data = json.loads(json_path.read_text(encoding='utf-8'))
    results = data.get('results', [])
    # We'll simulate each signal
    all_trades = []
    for signal in results:
        if not signal.get('ok'):
            continue
        stock_code = signal.get('stock_code')
        entry_date_str = signal.get('entry_trading_date')
        if not stock_code or not entry_date_str:
            continue
        entry_date = parse_day(entry_date_str)
        print(f"Processing {stock_code} on {entry_date}...")
        bars = fetch_bars_for_day(sb, stock_code, entry_date)
        if not bars:
            print(f"  No bars found for {stock_code} on {entry_date}")
            continue
        # Run simulation
        trade = simulate_fujimoto_126_trade(
            bars,
            min_score=60.0,
            stop_loss_pct=-2.0,
            take_profit_pct=3.0,
            take_profit_half_pct=5.0,
            time_exit="15:20",
            fee_bps=23.0,
            slippage_bps=10.0
        )
        trade['stock_code'] = stock_code
        trade['entry_date'] = entry_date_str
        all_trades.append(trade)
        print(f"  Result: ok={trade.get('ok')}, net_return={trade.get('net_return_pct')}, exit_reason={trade.get('exit_reason')}")
    # Summary
    print("\n=== Summary ===")
    successful = [t for t in all_trades if t.get('ok')]
    if successful:
        returns = [t['net_return_pct'] for t in successful if t.get('net_return_pct') is not None]
        if returns:
            avg_return = sum(returns) / len(returns)
            positive_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
            print(f"Successful trades: {len(successful)}/{len(all_trades)}")
            print(f"Average net return: {avg_return:.4f}%")
            print(f"Positive rate: {positive_rate:.2f}%")
            print(f"Min return: {min(returns):.4f}%")
            print(f"Max return: {max(returns):.4f}%")
        else:
            print("No returns available.")
    else:
        print("No successful trades.")
    # Print details
    for t in successful:
        print(f"{t['stock_code']} {t['entry_date']}: entry={t.get('entry_price')}, exit={t.get('exit_price')}, reason={t.get('exit_reason')}, net={t.get('net_return_pct')}%")

if __name__ == '__main__':
    main()