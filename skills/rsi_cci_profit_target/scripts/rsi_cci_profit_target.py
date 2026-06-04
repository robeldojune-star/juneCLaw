#!/usr/bin/env python3
"""
RSI‑CCI disparity20 entry with fixed profit target exit.
Usage:
    python3 rsi_cci_profit_target.py --stock 042660 --end-date 20260601 --lookback 5 --profit-target 1.5 [--show-plots]
"""

import sys
import argparse
from datetime import datetime, timedelta

# Add project root to path so we can import Hermes core modules if needed
sys.path.insert(0, '/home/june/trading')
from core.kiwoom_client import KiwoomAPIClient
from core.market_data_service import MarketDataService

import pandas as pd
import numpy as np


def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(com=period-1, adjust=False).mean()
    ma_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))


def main():
    parser = argparse.ArgumentParser(description='Disparity20/CCI entry with profit target exit')
    parser.add_argument('--stock', type=str, default='042660', help='Stock 6-digit code (e.g., 042660)')
    parser.add_argument('--end-date', type=str, default=datetime.now().strftime('%Y%m%d'), help='End date YYYYMMDD inclusive')
    parser.add_argument('--lookback', type=int, default=5, help='Number of trading days to include')
    parser.add_argument('--profit-target', type=float, default=1.5, help='Target profit percent for exit')
    parser.add_argument('--show-plots', action='store_true', help='Show matplotlib plot of equity curve')
    args = parser.parse_args()

    client = KiwoomAPIClient.from_env()
    mkt = MarketDataService(client)

    # Generate list of target dates (as strings) from oldest to newest
    end_date = datetime.strptime(args.end_date, '%Y%m%d')
    dates = [end_date - timedelta(days=i) for i in range(args.lookback, -1, -1)]
    date_strings = [d.strftime('%Y%m%d') for d in dates]

    all_trade_details = []  # collect across days for overall stats
    daily_summary = []      # for per-day print

    for target_date_str in date_strings:
        target_dt = datetime.strptime(target_date_str, '%Y%m%d')
        prev_dt = target_dt - timedelta(days=1)
        prev_date_str = prev_dt.strftime('%Y%m%d')

        bars_target = mkt.get_minute_chart_raw(args.stock, base_dt=target_date_str, minute_scope='1', adjusted_price=True)
        bars_prev = mkt.get_minute_chart_raw(args.stock, base_dt=prev_date_str, minute_scope='1', adjusted_price=True) if prev_dt >= datetime(2020,1,1) else []

        bars_all = (bars_prev or []) + (bars_target or [])
        if not bars_all:
            daily_summary.append((target_date_str, 0, 0, 'No data'))
            continue

        df = pd.DataFrame(bars_all)
        df = df.rename(columns={
            'cntr_tm': 'time',
            'open_pric': 'open',
            'high_pric': 'high',
            'low_pric': 'low',
            'cur_prc': 'close',
            'trde_qty': 'volume'
        })
        df = df[['time','open','high','low','close','volume']]
        for col in ['open','high','low','close','volume']:
            df[col] = abs(pd.to_numeric(df[col], errors='coerce'))
        df['time'] = pd.to_datetime(df['time'], format='%Y%m%d%H%M%S')
        df = df.sort_values('time').reset_index(drop=True)

        # Indicators
        df['ma20'] = df['close'].rolling(20).mean()
        df['disparity20'] = df['close'] / df['ma20'] * 100
        tp = (df['high'] + df['low'] + df['close']) / 3
        ma_tp = tp.rolling(20).mean()
        md = (tp - ma_tp).abs().rolling(20).mean()
        df['cci'] = (tp - ma_tp) / (0.015 * md)
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['rsi'] = rsi(df['close'], 14)

        # Buy signal per spec
        df['buy_signal_raw'] = (df['disparity20'] <= 100) & (df['cci'].shift(1) <= -100) & (df['cci'] > -100) & (df['volume'] >= df['vol_ma20'])
        df['buy_signal'] = df['buy_signal_raw'] & (~df['buy_signal_raw'].shift(1).fillna(False))

        # Filter to target date only
        target_date = target_dt.date()
        df_target = df[df['time'].dt.date == target_date]

        in_position = False
        entry_price = None
        entry_time = None

        for idx, row in df_target.iterrows():
            if row['buy_signal'] and not in_position:
                in_position = True
                entry_price = row['close']
                entry_time = row['time']
            elif in_position:
                profit_pct = (row['close'] - entry_price) / entry_price * 100.0
                if profit_pct >= args.profit_target:
                    all_trade_details.append({
                        'date': target_date_str,
                        'entry_time': entry_time,
                        'entry_price': entry_price,
                        'exit_time': row['time'],
                        'exit_price': row['close'],
                        'profit_pct': profit_pct
                    })
                    in_position = False
                    entry_price = None
                    entry_time = None
        # If position remains open at end of day, we ignore (no loss-cut)

        # Count signals for daily summary
        buy_signals = df_target[df_target['buy_signal']]
        sell_signals = df_target[(df_target['rsi'].shift(1) >= 70) & (df_target['rsi'] < 70)]  # just for reference, not used
        daily_summary.append((target_date_str, len(buy_signals), len(sell_signals), ''))

    # Print daily summary table
    print('Date       Buy  Sell  Notes')
    print('-----------------------------')
    for date_str, buy_cnt, sell_cnt, note in daily_summary:
        print(f'{date_str}  {buy_cnt:>3}  {sell_cnt:>4}  {note}')

    # Overall trade stats
    if all_trade_details:
        profits = [t['profit_pct'] for t in all_trade_details]
        win_rate = sum(1 for p in profits if p > 0) / len(profits) * 100
        avg_profit = np.mean(profits)
        print(f'\nTotal trades: {len(profits)}')
        print(f'Win rate: {win_rate:.2f}%')
        print(f'Average profit per trade: {avg_profit:.2f}%')
        print(f'Profits: {[round(p,2) for p in profits]}')

        if args.show_plots:
            try:
                import matplotlib.pyplot as plt
                # equity curve
                cumulative = np.cumprod([1 + p/100 for p in profits])
                plt.figure(figsize=(10,5))
                plt.plot(range(1, len(profits)+1), cumulative, marker='o')
                plt.title('Equity Curve (Profit Target Exit)')
                plt.xlabel('Trade #')
                plt.ylabel('Cumulative Return (x)')
                plt.grid(True)
                plt.show()
            except Exception as e:
                print(f'Could not display plot: {e}')
    else:
        print('\nNo completed trades found.')


if __name__ == '__main__':
    main()