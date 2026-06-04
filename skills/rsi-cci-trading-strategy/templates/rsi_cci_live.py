#!/usr/bin/env python3
# Template for RSI-CCI trading strategy
# Copy this file and modify parameters, indicators, or signal logic as needed.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'trading'))
from core.kiwoom_client import KiwoomAPIClient
from core.market_data_service import MarketDataService
import pandas as pd
import numpy as np

# ----- USER PARAMETERS -----
stock_code = '000000'   # e.g., '042660' for 한화오션
date_str   = 'YYYYMMDD' # e.g., '20260601'

# ----- INITIALIZE KIWOOM CLIENT -----
client = KiwoomAPIClient.from_env()   # reads .env, uses TRADING_ENV
mkt    = MarketDataService(client)

# ----- FETCH 1‑MINUTE BARS -----
bars_raw = mkt.get_minute_chart_raw(stock_code, base_dt=date_str, minute_scope='1', adjusted_price=True)
if not bars_raw:
    sys.exit('No data returned')

# ----- DATAFRAME PREP -----
df = pd.DataFrame(bars_raw)
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
    df[col] = pd.to_numeric(df[col], errors='coerce')
df['time'] = pd.to_datetime(df['time'], format='%Y%m%d%H%M%S')
df = df.sort_values('time').reset_index(drop=True)

# ----- INDICATORS (example: adjust periods as needed) -----
# 20‑day moving average of close
df['ma20'] = df['close'].rolling(20).mean()
# Disparity: (close / MA20) * 100
df['disparity20'] = df['close'] / df['ma20'] * 100

# CCI (Typical Price)
tp = (df['high'] + df['low'] + df['close']) / 3
ma_tp = tp.rolling(20).mean()
md = (tp - ma_tp).abs().rolling(20).mean()
df['cci'] = (tp - ma_tp) / (0.015 * md)

# Volume MA20
df['vol_ma20'] = df['volume'].rolling(20).mean()

# ----- RSI -----
def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(com=period-1, adjust=False).mean()
    ma_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))
df['rsi'] = rsi(df['close'], 14)

# ----- SIGNALS (customize these) -----
# Buy: disparity <= 95, prior CCI <= -100, current CCI > -100, volume >= vol_ma20
df['buy_signal_raw'] = (
    (df['disparity20'] <= 95) &
    (df['cci'].shift(1) <= -100) &
    (df['cci'] > -100) &
    (df['volume'] >= df['vol_ma20'])
)
df['buy_signal'] = df['buy_signal_raw'] & (~df['buy_signal_raw'].shift(1).fillna(False))

# Sell: RSI crossing down from >=70 to <70
df['sell_signal_raw'] = (df['rsi'].shift(1) >= 70) & (df['rsi'] < 70)
df['sell_signal'] = df['sell_signal_raw'] & (~df['sell_signal_raw'].shift(1).fillna(False))

# ----- OUTPUT -----
buy_signals  = df.loc[df['buy_signal'], ['time','close','disparity20','cci','volume','vol_ma20']]
sell_signals = df.loc[df['sell_signal'], ['time','close','disparity20','cci','volume','vol_ma20']]

print('=== Buy Signals ===')
print(buy_signals.to_string(index=False) if not buy_signals.empty else 'No buy signals')
print('\\n=== Sell Signals ===')
print(sell_signals.to_string(index=False) if not sell_signals.empty else 'No sell signals')