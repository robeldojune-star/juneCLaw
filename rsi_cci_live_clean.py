#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/june/trading')
from core.kiwoom_client import KiwoomAPIClient
from core.market_data_service import MarketDataService
import pandas as pd
import numpy as np

# ----- Parameters -----
stock_code = '042660'   # 한화오션
date_str   = '20260601' # YYYYMMDD

# ----- Initialize Kiwoom client -----
client = KiwoomAPIClient.from_env()   # reads .env, uses TRADING_ENV
mkt    = MarketDataService(client)

# ----- Fetch 1‑minute bars via ka10080 -----
bars_raw = mkt.get_minute_chart_raw(stock_code, base_dt=date_str, minute_scope='1', adjusted_price=True)
print(f'Fetched {len(bars_raw)} raw minute bars')
if not bars_raw:
    sys.exit('No data returned')

# ----- Convert to DataFrame and rename columns -----
df = pd.DataFrame(bars_raw)
# Expected keys: cntr_tm, open_pric, high_pric, low_pric, cur_prc, trde_qty, ...
df = df.rename(columns={
    'cntr_tm':   'time',
    'open_pric': 'open',
    'high_pric': 'high',
    'low_pric':  'low',
    'cur_prc':   'close',
    'trde_qty':  'volume'
})
# Keep only needed columns
df = df[['time','open','high','low','close','volume']]

# Convert to numeric (Kiwoom returns strings like '+126400') and take absolute value
for col in ['open','high','low','close','volume']:
    df[col] = abs(pd.to_numeric(df[col], errors='coerce'))

# Parse time
df['time'] = pd.to_datetime(df['time'], format='%Y%m%d%H%M%S')
# Filter to only the requested date
target_date = pd.to_datetime(date_str).date()
df = df[df['time'].dt.date == target_date]
df = df.sort_values('time').reset_index(drop=True)

if df.empty:
    print('No data for the specified date after filtering.')
    sys.exit(0)

# ----- Indicators per user specification -----
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

# ----- RSI calculation -----
def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(com=period-1, adjust=False).mean()
    ma_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

df['rsi'] = rsi(df['close'], 14)

# ----- Buy signal per user spec -----
# (disparity20 <= 95) & (cci.shift(1) <= -100) & (cci > -100) & (volume >= vol_ma20)
df['buy_signal_raw'] = (
    (df['disparity20'] <= 95) &
    (df['cci'].shift(1) <= -100) &
    (df['cci'] > -100) &
    (df['volume'] >= df['vol_ma20'])
)
# Edge‑triggered: only on the bar where condition turns True
df['buy_signal'] = df['buy_signal_raw'] & (~df['buy_signal_raw'].shift(1).fillna(False))

# ----- Sell signal per user request: RSI crossing down from >=70 to <70 -----
df['sell_signal_raw'] = (df['rsi'].shift(1) >= 70) & (df['rsi'] < 70)
df['sell_signal'] = df['sell_signal_raw'] & (~df['sell_signal_raw'].shift(1).fillna(False))

# ----- Output signals -----
buy_signals  = df.loc[df['buy_signal'], ['time','close','disparity20','cci','volume','vol_ma20']]
sell_signals = df.loc[df['sell_signal'], ['time','close','disparity20','cci','volume','vol_ma20']]

print('\n=== Buy Signals (disparity20 <= 95 & cci crossing -100 up & volume >= MA20) ===')
if buy_signals.empty:
    print('No buy signals found.')
else:
    print(buy_signals.to_string(index=False))
    print(f'Total buy signals: {len(buy_signals)}')

print('\n=== Sell Signals (RSI crossing down from >=70 to <70) ===')
if sell_signals.empty:
    print('No sell signals found.')
else:
    print(sell_signals.to_string(index=False))
    print(f'Total sell signals: {len(sell_signals)}')