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

# Get last 5 weekdays
end_date = datetime.now().date()
date_list = []
d = end_date
while len(date_list) < 5 and d >= end_date - timedelta(days=10):
    if d.weekday() < 5:
        date_list.append(d.strftime('%Y%m%d'))
    d -= timedelta(days=1)
date_list = sorted(date_list)

all_signals = []
trades = []
for date_str in date_list:
    try:
        bars_raw = mkt.get_minute_chart_raw(stock_code, base_dt=date_str, minute_scope='1', adjusted_price=True)
        if not bars_raw:
            print(f"{date_str}: no bars")
            continue
        df = pd.DataFrame(bars_raw)
        # Debug: show columns of first row
        if len(df) > 0:
            print(f"{date_str}: columns: {list(df.columns)}")
            print(f"{date_str}: first row: {df.iloc[0].to_dict()}")
        # Rename according to actual keys
        rename_map = {
            'cntr_tm': 'time',
            'open_pric': 'open',
            'high_pric': 'high',
            'low_pric': 'low',
            'cur_prc': 'close',
            'trde_qty': 'volume'
        }
        df = df.rename(columns=rename_map)
        # Keep only needed columns
        needed = ['time','open','high','low','close','volume']
        # Ensure all needed columns exist
        missing = [c for c in needed if c not in df.columns]
        if missing:
            print(f"{date_str}: missing columns {missing}, skipping")
            continue
        df = df[needed]
        for c in ['open','high','low','close','volume']:
            df[c] = abs(pd.to_numeric(df[c], errors='coerce'))
        df['time'] = pd.to_datetime(df['time'], format='%Y%m%d%H%M%S')
        df = df[df['time'].dt.date == pd.to_datetime(date_str).date()].copy()
        if df.empty:
            print(f"{date_str}: no data after date filter")
            continue
        df = df.sort_values('time').reset_index(drop=True)
        print(f"{date_str}: {len(df)} rows after processing")
        df = compute_signals(df)
        signals = df[df['entry_signal'] | df['exit_signal']][['time','close','rsi','cci','ma','entry_signal','exit_signal']].copy()
        signals['date'] = date_str
        all_signals.append(signals)
        # Pair signals for trade P&L
        entry_price = None
        entry_time = None
        for _, row in signals.iterrows():
            if row['entry_signal']:
                if entry_price is not None:
                    # consecutive entries without exit: close previous at this price? we'll just overwrite
                    pass
                entry_price = row['close']
                entry_time = row['time']
            elif row['exit_signal']:
                if entry_price is not None:
                    exit_price = row['close']
                    exit_time = row['time']
                    if exit_price > 0 and entry_price > 0:
                        ret = (exit_price - entry_price) / entry_price * 100.0
                        trades.append({
                            'date': date_str,
                            'entry_time': entry_time,
                            'exit_time': exit_time,
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'return_pct': ret
                        })
                    entry_price = None
                    entry_time = None
                else:
                    # exit without entry: ignore
                    pass
    except Exception as e:
        print(f"Error processing {date_str}: {e}")
        continue

# Output signals
if all_signals:
    result = pd.concat(all_signals, ignore_index=True)
    print('=== Signals (cleaned data, tuned params) over last', len(date_list), 'trading days ===')
    cols_to_show = ['date','time','close','rsi','cci','ma','entry_signal','exit_signal']
    print(result[cols_to_show].to_string(index=False))
    print()
else:
    print('No signals found.')

# Trade summary
if trades:
    returns = [t['return_pct'] for t in trades]
    win_trades = [r for r in returns if r > 0]
    loss_trades = [r for r in returns if r <= 0]
    print('=== Trade Performance (paired entry-exit) ===')
    print(f'Number of trades: {len(trades)}')
    print(f'Win rate: {len(win_trades)/len(trades)*100:.1f}%')
    print(f'Average return: {np.mean(returns):.2f}%')
    print(f'Median return: {np.median(returns):.2f}%')
    print(f'Best return: {np.max(returns):.2f}%')
    print(f'Worst return: {np.min(returns):.2f}%')
    print(f'Total return (sum): {np.sum(returns):.2f}%')
    # Show trades
    print()
    print('Trade details:')
    for t in trades:
        print(f"Date {t['date']} | Entry {t['entry_time']} @ {t['entry_price']:.0f} | Exit {t['exit_time']} @ {t['exit_price']:.0f} | Return {t['return_pct']:.2f}%")
else:
    print('No completed trades (entry followed by exit) found.')