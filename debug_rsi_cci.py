import sys
sys.path.insert(0, '.')
from core.kiwoom_client import KiwoomAPIClient
from core.market_data_service import MarketDataService
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Parameters
RSI_PERIOD = 10
CCI_PERIOD = 14
MA_PERIOD = 10
RSI_OVER = 70
RSI_UNDER = 30
CCI_OVER = 100
CCI_UNDER = -100

def rsi(series, period):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(com=period-1, adjust=False).mean()
    ma_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100/(1+rs))

def cci(high, low, close, period):
    tp = (high+low+close)/3
    ma = tp.rolling(window=period).mean()
    md = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x-x.mean())), raw=True)
    return (tp-ma)/(0.015*md)

def compute_signals(df):
    df['rsi'] = rsi(df['close'], RSI_PERIOD)
    df['cci'] = cci(df['high'], df['low'], df['close'], CCI_PERIOD)
    df['ma'] = df['close'].rolling(window=MA_PERIOD).mean()
    df['entry_raw'] = (df['rsi'] < RSI_UNDER) & (df['cci'] < CCI_UNDER) & (df['close'] > df['ma'])
    df['exit_raw']  = (df['rsi'] > RSI_OVER) & (df['cci'] > CCI_OVER) & (df['close'] < df['ma'])
    df['entry_signal'] = df['entry_raw'] & (~df['entry_raw'].shift(1).fillna(False))
    df['exit_signal']  = df['exit_raw']  & (~df['exit_raw'].shift(1).fillna(False))
    return df

client = KiwoomAPIClient.from_env()
mkt = MarketDataService(client)
stock_code = '042660'

# Just one day for debug
date_str = '20260601'
bars_raw = mkt.get_minute_chart_raw(stock_code, base_dt=date_str, minute_scope='1', adjusted_price=True)
if not bars_raw:
    sys.exit('no bars')
df = pd.DataFrame(bars_raw)
rename_map = {
    'cntr_tm': 'time',
    'open_pric': 'open',
    'high_pric': 'high',
    'low_pric': 'low',
    'cur_prc': 'close',
    'trde_qty': 'volume'
}
df = df.rename(columns=rename_map)
needed = ['time','open','high','low','close','volume']
df = df[needed]
for c in ['open','high','low','close','volume']:
    df[c] = abs(pd.to_numeric(df[c], errors='coerce'))
df['time'] = pd.to_datetime(df['time'], format='%Y%m%d%H%M%S')
df = df[df['time'].dt.date == pd.to_datetime(date_str).date()].copy()
df = df.sort_values('time').reset_index(drop=True)
print(f'Rows: {len(df)}')
df = compute_signals(df)
print('RSI stats:', df['rsi'].describe())
print('CCI stats:', df['cci'].describe())
print('MA stats:', df['ma'].describe())
print('Close vs MA >?', (df['close'] > df['ma']).sum())
print('RSI<30?', (df['rsi'] < RSI_UNDER).sum())
print('CCI<-100?', (df['cci'] < CCI_UNDER).sum())
print('Entry raw count:', df['entry_raw'].sum())
print('Exit raw count:', df['exit_raw'].sum())
print('Entry signal count:', df['entry_signal'].sum())
print('Exit signal count:', df['exit_signal'].sum())
# Show a few rows where conditions near
df['entry_components'] = (df['rsi'] < RSI_UNDER).astype(int) + (df['cci'] < CCI_UNDER).astype(int) + (df['close'] > df['ma']).astype(int)
print('Rows with 2/3 components:', (df['entry_components'] >= 2).sum())
print('Rows with 3/3 components:', (df['entry_components'] == 3).sum())
if (df['entry_components'] == 3).any():
    print(df.loc[df['entry_components'] == 3, ['time','close','rsi','cci','ma']].head())