import sys
sys.path.insert(0, '/home/june/trading')
import pandas as pd
import numpy as np

stock_code = '042660'
date_str = '20260601'
csv_path = f'/home/june/trading/data/intraday/{stock_code}_{date_str}.csv'
df = pd.read_csv(csv_path, parse_dates=['time'])
df = df.rename(columns={'cntr_tm':'time','open_pric':'open','high_pric':'high','low_pric':'low','close_pric':'close','trde_qty':'volume'}) if 'cntr_tm' in df.columns else df
needed = ['time','open','high','low','close','volume']
df = df[needed]
for c in ['open','high','low','close','volume']:
    df[c] = pd.to_numeric(df[c], errors='coerce')
df['time'] = pd.to_datetime(df['time'])
df = df.sort_values('time').reset_index(drop=True)

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

df['rsi'] = rsi(df['close'], RSI_PERIOD)
df['cci'] = cci(df['high'], df['low'], df['close'], CCI_PERIOD)
df['ma'] = df['close'].rolling(window=MA_PERIOD).mean()

print('RSI min:', df['rsi'].min(), 'at', df.loc[df['rsi'].idxmin(), 'time'] if not df['rsi'].isnull().all() else 'None')
print('RSI max:', df['rsi'].max(), 'at', df.loc[df['rsi'].idxmax(), 'time'] if not df['rsi'].isnull().all() else 'None')
print('CCI min:', df['cci'].min(), 'at', df.loc[df['cci'].idxmin(), 'time'] if not df['cci'].isnull().all() else 'None')
print('CCI max:', df['cci'].max(), 'at', df.loc[df['cci'].idxmax(), 'time'] if not df['cci'].isnull().all() else 'None')
print('Close > MA count:', (df['close'] > df['ma']).sum())
print('Close < MA count:', (df['close'] < df['ma']).sum())

df['entry_raw'] = (df['rsi'] < RSI_UNDER) & (df['cci'] < CCI_UNDER) & (df['close'] > df['ma'])
df['exit_raw']  = (df['rsi'] > RSI_OVER) & (df['cci'] > CCI_OVER) & (df['close'] < df['ma'])
print('Entry raw count:', df['entry_raw'].sum())
print('Exit raw count:', df['exit_raw'].sum())
if df['entry_raw'].any():
    print('Entry rows:')
    print(df.loc[df['entry_raw'], ['time','close','rsi','cci','ma']].head())
if df['exit_raw'].any():
    print('Exit rows:')
    print(df.loc[df['exit_raw'], ['time','close','rsi','cci','ma']].head())