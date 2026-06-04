import sys
sys.path.insert(0, '/home/june/trading')
import pandas as pd
import numpy as np

# Use sample CSV
stock_code = '042660'
date_str = '20260601'
csv_path = f'/home/june/trading/data/intraday/{stock_code}_{date_str}.csv'
df = pd.read_csv(csv_path, parse_dates=['time'])
print(f'Loaded {len(df)} rows from {csv_path}')
# Ensure columns
df = df.rename(columns={'cntr_tm':'time','open_pric':'open','high_pric':'high','low_pric':'low','close_pric':'close','trde_qty':'volume'}) if 'cntr_tm' in df.columns else df
# Keep needed
needed = ['time','open','high','low','close','volume']
df = df[needed]
for c in ['open','high','low','close','volume']:
    df[c] = pd.to_numeric(df[c], errors='coerce')
df['time'] = pd.to_datetime(df['time'])
df = df.sort_values('time').reset_index(drop=True)

# Parameters as requested a,b,c: RSI=10, CCI=14, MA=10
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
df['entry_raw'] = (df['rsi'] < RSI_UNDER) & (df['cci'] < CCI_UNDER) & (df['close'] > df['ma'])
df['exit_raw']  = (df['rsi'] > RSI_OVER) & (df['cci'] > CCI_OVER) & (df['close'] < df['ma'])
df['entry_signal'] = df['entry_raw'] & (~df['entry_raw'].shift(1).fillna(False))
df['exit_signal']  = df['exit_raw']  & (~df['exit_raw'].shift(1).fillna(False))

signals = df[df['entry_signal'] | df['exit_signal']][['time','close','rsi','cci','ma','entry_signal','exit_signal']]
print('\n=== Signals ===')
if signals.empty:
    print('No signals')
else:
    print(signals.to_string(index=False))
    entries = signals['entry_signal'].sum()
    exits = signals['exit_signal'].sum()
    print('Entries:', int(entries), 'Exits:', int(exits))
    # Simple trade P&L assuming entry then exit alternation
    entry_price = None
    returns = []
    for _, row in signals.iterrows():
        if row['entry_signal']:
            entry_price = row['close']
        elif row['exit_signal'] and entry_price is not None:
            exit_price = row['close']
            ret = (exit_price - entry_price) / entry_price * 100.0
            returns.append(ret)
            entry_price = None
    if returns:
        print(f'Number of trades: {len(returns)}')
        print(f'Average return: {np.mean(returns):.2f}%')
        print(f'Win rate: {sum(1 for r in returns if r>0)/len(returns)*100:.1f}%')
    else:
        print('No completed entry-exit pairs found.')