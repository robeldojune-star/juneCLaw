#!/usr/bin/env python3
"""
Disparity20 + CCI + Volume buy signal strategy
- Buy when:
    * disparity20 <= 95   (price is >=5% below 20‑day MA)
    * CCI crosses up -100 (previous CCI <= -100 and current CCI > -100)
    * volume >= 20‑period average volume
- Uses Kiwoom ka10080 1‑minute bars for the given date.
- Outputs detected buy signals (timestamp, price, indicators).
"""

import sys
sys.path.insert(0, '/home/june/trading')
from core.kiwoom_client import KiwoomAPIClient
from core.market_data_service import MarketDataService
import pandas as pd
import numpy as np

# ----- Parameters -----
stock_code = '042660'   # 한화오션 (change as needed)
date_str   = '20260601' # YYYYMMDD (today)

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
df = df.rename(columns={
    'cntr_tm':   'time',
    'open_pric': 'open',
    'high_pric': 'high',
    'low_pric':  'low',
    'cur_prc':   'close',
    'trde_qty':  'volume'
})
df = df[['time','open','high','low','close','volume']]

# Convert to numeric (Kiwoom returns strings like '+126400')
for col in ['open','high','low','close','volume']:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Parse time
df['time'] = pd.to_datetime(df['time'], format='%Y%m%d%H%M%S')
df = df.sort_values('time').reset_index(drop=True)

# ----- Indicators -----
# 20‑period moving average of close
df['ma20'] = df['close'].rolling(window=20).mean()
# Disparity (%): price relative to MA20
df['disparity20'] = df['close'] / df['ma20'] * 100

# Typical Price and CCI (20)
tp = (df['high'] + df['low'] + df['close']) / 3
ma_tp = tp.rolling(window=20).mean()
md = (tp - ma_tp).abs().rolling(window=20).mean()
df['cci'] = (tp - ma_tp) / (0.015 * md)

# 20‑period volume average
df['vol_ma20'] = df['volume'].rolling(window=20).mean()

# ----- Buy signal -----
df['buy_signal'] = (
    (df['disparity20'] <= 95) &
    (df['cci'].shift(1) <= -100) &
    (df['cci'] > -100) &
    (df['volume'] >= df['vol_ma20'])
)
# Edge‑triggered: only on the bar where condition turns True
df['buy_signal'] = df['buy_signal'] & (~df['buy_signal'].shift(1).fillna(False))

# ----- Output -----
signals = df[df['buy_signal']][['time','close','disparity20','cci','volume','vol_ma20','ma20']]
print('\n=== Detected BUY Signals ===')
if signals.empty:
    print('No buy signals found.')
else:
    print(signals.to_string(index=False))
    print(f'\nTotal buy signals: {len(signals)}')