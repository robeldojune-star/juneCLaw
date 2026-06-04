#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/june/trading')
from core.kiwoom_client import KiwoomAPIClient
from core.market_data_service import MarketDataService
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ----- Parameters -----
stock_code = '042660'   # 한화오션
end_date_str = '20260601' # YYYYMMDD, inclusive
lookback_days = 4  # total 5 days including end_date

# ----- Initialize Kiwoom client -----
client = KiwoomAPIClient.from_env()
mkt = MarketDataService(client)

def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(com=period-1, adjust=False).mean()
    ma_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

# We'll collect per buy signal: entry time, price, then compute max later close within same day
results = []

# Generate list of target dates (as strings)
end_date = datetime.strptime(end_date_str, '%Y%m%d')
dates = [end_date - timedelta(days=i) for i in range(lookback_days, -1, -1)]  # from oldest to newest
date_strings = [d.strftime('%Y%m%d') for d in dates]

for target_date_str in date_strings:
    target_dt = datetime.strptime(target_date_str, '%Y%m%d')
    prev_dt = target_dt - timedelta(days=1)
    prev_date_str = prev_dt.strftime('%Y%m%d')
    
    bars_target = mkt.get_minute_chart_raw(stock_code, base_dt=target_date_str, minute_scope='1', adjusted_price=True)
    bars_prev = mkt.get_minute_chart_raw(stock_code, base_dt=prev_date_str, minute_scope='1', adjusted_price=True) if prev_dt >= datetime(2020,1,1) else []
    
    bars_all = (bars_prev or []) + (bars_target or [])
    if not bars_all:
        continue
    
    df = pd.DataFrame(bars_all)
    df = df.rename(columns={
        'cntr_tm':   'time',
        'open_pric': 'open',
        'high_pric': 'high',
        'low_pric':  'low',
        'cur_prc':   'close',
        'trde_qty':  'volume'
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
    
    buy_indices = df_target.index[df_target['buy_signal']].tolist()
    for idx in buy_indices:
        entry_price = df_target.at[idx, 'close']
        entry_time = df_target.at[idx, 'time']
        # Look forward from next index to end of day
        later = df_target.loc[idx+1:]
        if later.empty:
            max_profit = 0.0
            exit_time = entry_time
            exit_price = entry_price
        else:
            # compute profit series
            profit_series = (later['close'] - entry_price) / entry_price * 100.0
            max_profit = profit_series.max()
            # get time of max profit (first occurrence)
            max_idx = profit_series.idxmax()
            exit_time = df_target.at[max_idx, 'time']
            exit_price = df_target.at[max_idx, 'close']
        results.append({
            'date': target_date_str,
            'entry_time': entry_time,
            'entry_price': entry_price,
            'exit_time': exit_time,
            'exit_price': exit_price,
            'max_profit_pct': max_profit
        })

if results:
    df_res = pd.DataFrame(results)
    print(f"Total buy signals: {len(df_res)}")
    print(f"Buy signals achieving >=1.5% profit later same day: {(df_res['max_profit_pct'] >= 1.5).sum()}")
    print(f"Average max profit per signal: {df_res['max_profit_pct'].mean():.2f}%")
    print(f"Median max profit: {df_res['max_profit_pct'].median():.2f}%")
    print(f"Best case profit: {df_res['max_profit_pct'].max():.2f}%")
    print("\nDetails (showing top 5 by max profit):")
    top = df_res.nlargest(5, 'max_profit_pct')
    for _, row in top.iterrows():
        print(f"  {row['date']} {row['entry_time']} @ {row['entry_price']:.0f} -> max {row['max_profit_pct']:.2f}% at {row['exit_time']} @ {row['exit_price']:.0f}")
else:
    print('No buy signals found.')
