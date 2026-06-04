# shared/strategy.py
# Common indicator and signal logic for RSI/CCI disparity strategy

import pandas as pd
import numpy as np

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate technical indicators:
    - MA20 of close
    - Disparity20 = (close / MA20) * 100
    - CCI (20 period)
    - RSI (14 period)
    - Volume MA20
    Assumes df has columns: ['open','high','low','close','volume'] and a datetime index or 'time' column.
    Returns a copy with new columns.
    """
    df = df.copy()
    # Ensure numeric
    for col in ['open','high','low','close','volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # MA20
    df['ma20'] = df['close'].rolling(20).mean()
    # Disparity20
    df['disparity20'] = df['close'] / df['ma20'] * 100
    
    # CCI
    tp = (df['high'] + df['low'] + df['close']) / 3
    ma_tp = tp.rolling(20).mean()
    md = (tp - ma_tp).abs().rolling(20).mean()
    df['cci'] = (tp - ma_tp) / (0.015 * md)
    
    # Volume MA20
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    
    # RSI (14)
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(com=13, adjust=False).mean()  # com = period-1
    ma_down = down.ewm(com=13, adjust=False).mean()
    rs = ma_up / ma_down
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def generate_signals_profit_target(df: pd.DataFrame, profit_target_pct: float = 1.5) -> pd.DataFrame:
    """Generate buy signals only (same entry as generate_signals).
    Sell signal is triggered when price reaches +profit_target_pct% from buy entry.
    RSI-based exits are disabled for this variant.
    """
    df = df.copy()
    # Buy signal raw
    df['buy_signal_raw'] = (
        (df['disparity20'] <= 100) &
        (df['cci'].shift(1) <= -100) &
        (df['cci'] > -100) &
        (df['volume'] >= df['vol_ma20'])
    )
    df['buy_signal'] = df['buy_signal_raw'] & (~df['buy_signal_raw'].shift(1).fillna(False))

    # Profit-target sell: track buy price and fire sell when close >= buy * (1 + pt/100)
    buy_price = None
    sell_signal = pd.Series(False, index=df.index)
    for i, (idx, row) in enumerate(df.iterrows()):
        if df.at[idx, 'buy_signal']:
            buy_price = row['close']
        if buy_price is not None:
            target = buy_price * (1 + profit_target_pct / 100)
            if row['high'] >= target:
                sell_signal.at[idx] = True
                buy_price = None
    df['sell_signal_raw'] = sell_signal
    df['sell_signal'] = df['sell_signal_raw'] & (~df['sell_signal_raw'].shift(1).fillna(False))
    return df


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate buy and sell signals based on computed indicators.
    Buy: disparity20 <= 100 and CCI crosses -100 upward and volume >= vol_ma20
    Sell: RSI crosses down from >=70 to <70
    Signals are edge-triggered (only the bar where condition turns True).
    Returns dataframe with added columns:
        'buy_signal_raw', 'buy_signal',
        'sell_signal_raw', 'sell_signal'
    """
    df = df.copy()
    # Buy signal raw
    df['buy_signal_raw'] = (
        (df['disparity20'] <= 100) &
        (df['cci'].shift(1) <= -100) &
        (df['cci'] > -100) &
        (df['volume'] >= df['vol_ma20'])
    )
    # Edge-triggered
    df['buy_signal'] = df['buy_signal_raw'] & (~df['buy_signal_raw'].shift(1).fillna(False))
    
    # Sell signal raw: RSI crossing down from >=70 to <70
    df['sell_signal_raw'] = (df['rsi'].shift(1) >= 70) & (df['rsi'] < 70)
    df['sell_signal'] = df['sell_signal_raw'] & (~df['sell_signal_raw'].shift(1).fillna(False))
    
    return df