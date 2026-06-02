#!/usr/bin/env python3
"""
RSI(14) mean-reversion backtest on KOSPI Top 50 using daily prices.
- Entry: RSI(14) <= 30 (oversold) on day t
- Enter at open of day t+1 (to avoid lookahead)
- Exit: 
   * Stop loss: -1% from entry price
   * Take profit: +3% from entry price (close position)
   * Max holding: 3 days (including entry day)
   * If neither hit, exit at close of day t+3 (or last available)
- Uses daily price table (open, high, low, close) from Supabase.
"""
import sys
import json
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import math
from collections import defaultdict

sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient

KST = timezone(timedelta(hours=9))

def load_kospi_top50(csv_path='/home/june/trading/data/kospi_top50_common_stocks_marketcap_naver.csv'):
    codes = []
    try:
        with open(csv_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get('종목코드')
                if code:
                    codes.append(code.strip())
    except Exception as e:
        print(f"Failed to load KOSPI Top 50 list: {e}")
        codes = []
    # deduplicate preserving order
    seen = set()
    deduped = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped

KOSPI_TOP_50 = load_kospi_top50()
print(f"Loaded {len(KOSPI_TOP_50)} stocks from KOSPI Top 50 list.")

def rsi_series(closes, period=14):
    """Return list of RSI values (same length as closes)."""
    if len(closes) < period + 1:
        return [None] * len(closes)
    rsi = [None] * len(closes)
    gains = []
    losses = []
    for i in range(1, period + 1):
        delta = closes[i] - closes[i-1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rsi[period] = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i-1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rsi[i] = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    return rsi

def fetch_daily_prices(sb, stock_code, start_date, end_date):
    """Fetch daily prices for given stock and date range inclusive."""
    rows = sb.get('daily_prices', {
        'stock_code': f'eq.{stock_code}',
        'date': f'gte.{start_date.isoformat()}',
        'date': f'lte.{end_date.isoformat()}'
    }, timeout=20)
    rows.sort(key=lambda r: r['date'])
    prices = {}
    for r in rows:
        dt = datetime.fromisoformat(r['date']).date()
        prices[dt] = {
            'open': float(r['open']),
            'high': float(r['high']),
            'low': float(r['low']),
            'close': float(r['close']),
            'volume': int(r['volume'] or 0)
        }
    return prices

def simulate_rsi_mean_reversion(prices_dict, rsi_dict, entry_offset=1, stop_loss_pct=-1.0, take_profit_pct=3.0, max_holding_days=3):
    """
    prices_dict: mapping date -> {open, high, low, close}
    rsi_dict: mapping date -> rsi value (or None)
    Returns list of trade results (net_return_pct) and stats.
    """
    trades = []
    dates = sorted(prices_dict.keys())
    for i, dt in enumerate(dates):
        rsi_val = rsi_dict.get(dt)
        if rsi_val is None or rsi_val > 30:
            continue
        # entry date is next trading day
        try:
            idx = dates.index(dt)
        except ValueError:
            continue
        if idx + entry_offset >= len(dates):
            continue  # no future data
        entry_date = dates[idx + entry_offset]
        entry_price = prices_dict[entry_date]['open']
        # determine exit: we will check each subsequent day up to max_holding_days
        exit_price = None
        exit_date = None
        exit_reason = None
        for hold in range(1, max_holding_days + 1):
            exit_idx = idx + entry_offset + hold - 1  # hold=1 => entry_date itself
            if exit_idx >= len(dates):
                break
            check_date = dates[exit_idx]
            high = prices_dict[check_date]['high']
            low = prices_dict[check_date]['low']
            close = prices_dict[check_date]['close']
            # check stop loss
            if low <= entry_price * (1 + stop_loss_pct / 100.0):
                exit_price = entry_price * (1 + stop_loss_pct / 100.0)
                exit_date = check_date
                exit_reason = 'STOP_LOSS'
                break
            # check take profit
            if high >= entry_price * (1 + take_profit_pct / 100.0):
                exit_price = entry_price * (1 + take_profit_pct / 100.0)
                exit_date = check_date
                exit_reason = 'TAKE_PROFIT'
                break
            # if last holding day, exit at close
            if hold == max_holding_days:
                exit_price = close
                exit_date = check_date
                exit_reason = 'MAX_HOLDING'
                break
        if exit_price is None:
            # fell through because we ran out of dates
            exit_date = dates[-1]
            exit_price = prices_dict[exit_date]['close']
            exit_reason = 'END_OF_DATA'
        # compute return
        gross = (exit_price - entry_price) / entry_price * 100.0
        # cost: round-trip fee + slippage (23 bps + 10 bps) * 2 = 66 bps = 0.66%
        cost = 0.66
        net = gross - cost
        trades.append({
            'signal_date': dt.isoformat(),
            'entry_date': entry_date.isoformat(),
            'entry_price': round(entry_price, 2),
            'exit_date': exit_date.isoformat(),
            'exit_price': round(exit_price, 2),
            'exit_reason': exit_reason,
            'gross_return_pct': round(gross, 4),
            'net_return_pct': round(net, 4)
        })
    return trades

def main():
    sb = SupabaseRestClient()
    end_date = datetime.now(KST).date()
    start_date = end_date - timedelta(days=90)  # approx 3 months
    print(f"Backtesting from {start_date} to {end_date} (KST)")
    all_trades = []
    for stock_code in KOSPI_TOP_50[:10]:  # limit to first 10 for speed
        print(f"Processing {stock_code}...")
        prices = fetch_daily_prices(sb, stock_code, start_date, end_date)
        if not prices:
            print(f"  No price data.")
            continue
        closes = [prices[dt]['close'] for dt in sorted(prices.keys())]
        rsi_list = rsi_series(closes, period=14)
        # map date to rsi, filtering out None
        sorted_dates = sorted(prices.keys())
        rsi_dict = {}
        for i, dt in enumerate(sorted_dates):
            rsi_dict[dt] = rsi_list[i]
        trades = simulate_rsi_mean_reversion(prices, rsi_dict,
                                             entry_offset=1,
                                             stop_loss_pct=-1.0,
                                             take_profit_pct=3.0,
                                             max_holding_days=3)
        for t in trades:
            t['stock_code'] = stock_code
        all_trades.extend(trades)
        print(f"  Found {len(trades)} trades.")
    # Summary
    if all_trades:
        net_returns = [t['net_return_pct'] for t in all_trades]
        avg_return = sum(net_returns) / len(net_returns)
        positive_rate = sum(1 for r in net_returns if r > 0) / len(net_returns) * 100
        print(f"\n=== Summary ===")
        print(f"Total trades: {len(all_trades)}")
        print(f"Average net return: {avg_return:.4f}%")
        print(f"Positive rate: {positive_rate:.2f}%")
        print(f"Min return: {min(net_returns):.4f}%")
        print(f"Max return: {max(net_returns):.4f}%")
        # Save results
        out_path = Path('/home/june/trading/reports/rsi_mean_reversion_backtest.json')
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w') as f:
            json.dump({
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'date_range': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
                'trades': all_trades
            }, f, indent=2, ensure_ascii=False)
        print(f"\nDetailed results saved to {out_path}")
    else:
        print("No trades generated.")

if __name__ == '__main__':
    main()