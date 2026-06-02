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

def fetch_bars_for_kst_date(sb, stock_code, kst_date):
    """
    kst_date: datetime.date object (KST date)
    Returns list of PriceBar for that KST day.
    """
    # Start of day in KST
    start_kst = datetime.combine(kst_date, datetime.min.time()).replace(tzinfo=KST)
    # End of day in KST (exclusive)
    end_kst = start_kst + timedelta(days=1)
    # Convert to UTC
    start_utc = start_kst.astimezone(timezone.utc)
    end_utc = end_kst.astimezone(timezone.utc)
    # Format as ISO strings for filtering
    start_str = start_utc.isoformat()
    end_str = end_utc.isoformat()
    # Use gte and lt on timestamp
    params = {
        'stock_code': f'eq.{stock_code}',
        'source': f'eq.{SOURCE}',
        'time_frame': f'eq.{TIME_FRAME}',
        'timestamp': f'gte.{start_str}',
        'timestamp_lt': f'lt.{end_str}'
    }
    try:
        rows = sb.get('intraday_prices', params, timeout=30)
    except Exception as e:
        print(f"Error fetching rows for {stock_code} on {kst_date}: {e}")
        return []
    bars = []
    for row in rows:
        ts = row['timestamp']
        dt = ts_to_kst(ts)
        # dt should be within [start_kst, end_kst) but we trust the filter
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
    # Define stocks to test (top 5 by volume or just a few)
    stock_codes = ['005930', '000660', '005380', '035420', '068270']
    # Define date range: last 14 days from today (KST)
    end_date = datetime.now(KST).date()
    start_date = end_date - timedelta(days=13)  # inclusive
    print(f"Backtesting from {start_date} to {end_date} (KST) for stocks: {', '.join(stock_codes)}")
    all_results = []
    for stock_code in stock_codes:
        print(f"\n=== Processing {stock_code} ===")
        current = start_date
        while current <= end_date:
            bars = fetch_bars_for_kst_date(sb, stock_code, current)
            if not bars:
                # No data for this day (maybe weekend or holiday)
                current += timedelta(days=1)
                continue
            print(f"  {current}: {len(bars)} bars")
            # Run simulation
            trade = simulate_fujimoto_126_trade(
                bars,
                min_score=60.0,
                stop_loss_pct=-2.0,
                take_profit_pct=3.0,
                time_exit="15:20",
                fee_bps=23.0,
                slippage_bps=10.0
            )
            trade['stock_code'] = stock_code
            trade['date'] = current.isoformat()
            all_results.append(trade)
            if trade.get('ok'):
                print(f"    -> OK: entry={trade.get('entry_price')}, exit={trade.get('exit_price')}, reason={trade.get('exit_reason')}, net={trade.get('net_return_pct')}%")
            else:
                print(f"    -> Blocked: {trade.get('blocking_conditions')}")
            current += timedelta(days=1)
    # Summary
    print("\n=== Summary ===")
    successful = [r for r in all_results if r.get('ok')]
    if successful:
        returns = [r['net_return_pct'] for r in successful if r.get('net_return_pct') is not None]
        if returns:
            avg_return = sum(returns) / len(returns)
            positive_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
            print(f"Total days evaluated: {len(all_results)}")
            print(f"Successful trades: {len(successful)}/{len(all_results)}")
            print(f"Average net return: {avg_return:.4f}%")
            print(f"Positive rate: {positive_rate:.2f}%")
            print(f"Min return: {min(returns):.4f}%")
            print(f"Max return: {max(returns):.4f}%")
        else:
            print("No returns available.")
    else:
        print("No successful trades.")
    # Optionally save results to file
    out_path = Path('/home/june/trading/reports/fujimoto_126_backtest_rest.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'stocks': stock_codes,
            'date_range': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'results': all_results
        }, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed results saved to {out_path}")

if __name__ == '__main__':
    main()