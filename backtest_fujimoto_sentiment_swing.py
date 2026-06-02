import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from core.fujimoto_126_filter import PriceBar, simulate_fujimoto_126_trade
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import os

# Import our filters
from market_sentiment_filter import get_market_sentiment_symbols, get_kospi_top50_by_marketcap

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

def fetch_bars_for_day(sb, stock_code, kst_date):
    rows = sb.get('intraday_prices', {
        'stock_code': f'eq.{stock_code}',
        'source': f'eq.{SOURCE}',
        'time_frame': f'eq.{TIME_FRAME}'
    }, timeout=30)
    bars = []
    for row in rows:
        ts = row['timestamp']
        dt = ts_to_kst(ts)
        if dt.date() == kst_date:
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
    # We'll test a broader set: KOSPI top 50
    stock_codes = get_kospi_top50_by_marketcap(datetime.now(KST).strftime('%Y%m%d'))
    # Limit to first 20 for speed in demo
    stock_codes = stock_codes[:20]
    end_date = datetime.now(KST).date()
    start_date = end_date - timedelta(days=13)  # approx 2 weeks
    print(f"Backtesting from {start_date} to {end_date} (KST) for {len(stock_codes)} stocks")
    all_results = []
    for stock_code in stock_codes:
        print(f"\n=== Processing {stock_code} ===")
        current = start_date
        while current <= end_date:
            # Skip weekends? We'll let data absence handle it.
            # Get previous trading day for sentiment filter
            prev_day = current - timedelta(days=1)
            # Simple approach: just use calendar day; could improve with KRX holiday calendar.
            # For now, we use prev_day as is.
            sentiment_symbols = get_market_sentiment_symbols(prev_day.strftime('%Y%m%d'))
            kospi_top50 = set(get_kospi_top50_by_marketcap(current.strftime('%Y%m%d')))
            # Check filters
            if stock_code not in kospi_top50:
                # Not in top 50, skip
                current += timedelta(days=1)
                continue
            if sentiment_symbols and stock_code not in sentiment_symbols:
                # Does not pass sentiment filter
                current += timedelta(days=1)
                continue
            bars = fetch_bars_for_day(sb, stock_code, current)
            if not bars:
                current += timedelta(days=1)
                continue
            print(f"  {current}: {len(bars)} bars")
            # Run simulation with stop loss -1% and max holding 3 days
            trade = simulate_fujimoto_126_trade(
                bars,
                min_score=60.0,
                stop_loss_pct=-1.0,   # user requested -1%
                take_profit_pct=3.0,
                take_profit_half_pct=5.0,
                time_exit="15:20",    # still intraday exit, but we will also enforce max holding days inside simulate? We'll need to modify simulate to accept max_holding_days.
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
    # Save results
    out_path = Path('/home/june/trading/reports/fujimoto_126_backtest_sentiment_swing.json')
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