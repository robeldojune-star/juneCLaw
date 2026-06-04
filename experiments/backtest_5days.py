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

results = []

# Generate list of target dates (as strings)
end_date = datetime.strptime(end_date_str, '%Y%m%d')
dates = [end_date - timedelta(days=i) for i in range(lookback_days, -1, -1)]  # from oldest to newest
date_strings = [d.strftime('%Y%m%d') for d in dates]

for target_date_str in date_strings:
    # Fetch data for target day and previous calendar day (for warmup)
    target_dt = datetime.strptime(target_date_str, '%Y%m%d')
    prev_dt = target_dt - timedelta(days=1)
    prev_date_str = prev_dt.strftime('%Y%m%d')
    
    # Fetch target day's minute bars
    bars_target = mkt.get_minute_chart_raw(stock_code, base_dt=target_date_str, minute_scope='1', adjusted_price=True)
    # Fetch previous day's minute bars (may be empty if weekend/holiday)
    bars_prev = mkt.get_minute_chart_raw(stock_code, base_dt=prev_date_str, minute_scope='1', adjusted_price=True) if prev_dt >= datetime(2020,1,1) else []
    
    # Combine
    bars_all = (bars_prev or []) + (bars_target or [])
    if not bars_all:
        # No data at all
        results.append((target_date_str, 0, 0, 'No data'))
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
    
    def rsi_calc(series, period=14):
        d = series.diff()
        up = d.clip(lower=0)
        down = -d.clip(upper=0)
        ma_up = up.ewm(com=period-1, adjust=False).mean()
        ma_down = down.ewm(com=period-1, adjust=False).mean()
        rs = ma_up / ma_down
        return 100 - (100 / (1 + rs))
    df['rsi'] = rsi_calc(df['close'], 14)
    
    # Signals
    df['buy_signal_raw'] = (df['disparity20'] <= 100) & (df['cci'].shift(1) <= -100) & (df['cci'] > -100) & (df['volume'] >= df['vol_ma20'])
    df['buy_signal'] = df['buy_signal_raw'] & (~df['buy_signal_raw'].shift(1).fillna(False))
    
    df['sell_signal_raw'] = (df['rsi'].shift(1) >= 70) & (df['rsi'] < 70)
    df['sell_signal'] = df['sell_signal_raw'] & (~df['sell_signal_raw'].shift(1).fillna(False))
    
    # Filter to target date only
    target_date = target_dt.date()
    df_target = df[df['time'].dt.date == target_date]
    
    buy_signals = df_target[df_target['buy_signal']]
    sell_signals = df_target[df_target['sell_signal']]
    
    results.append((target_date_str, len(buy_signals), len(sell_signals), ''))

# Print summary
print('Date       Buy  Sell  Notes')
print('-----------------------------')
for date_str, buy_cnt, sell_cnt, note in results:
    print(f'{date_str}  {buy_cnt:>3}  {sell_cnt:>4}  {note}')