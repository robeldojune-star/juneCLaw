#!/usr/bin/env python3
"""Calculate daily technical indicators for active KOSPI TOP50.

Uses only rows already collected in daily_prices from Kiwoom. No fake data.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import psycopg

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env'


def load_env():
    env = {}
    for raw in ENV_PATH.read_text(encoding='utf-8', errors='replace').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        env[k.strip()] = v.split(' #', 1)[0].strip().strip('"').strip("'")
    return env


def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values('date').copy()
    for c in ['open','high','low','close','volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['ma_5'] = df['close'].rolling(5).mean()
    df['ma_20'] = df['close'].rolling(20).mean()
    df['ma_60'] = df['close'].rolling(60).mean()

    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    df['rsi'] = 100 - (100 / (1 + rs))

    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['signal_line'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['signal_line']

    df['bb_middle'] = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + 2 * bb_std
    df['bb_lower'] = df['bb_middle'] - 2 * bb_std

    prev_close = df['close'].shift(1)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - prev_close).abs(),
        (df['low'] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()

    direction = df['close'].diff().fillna(0).apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    df['obv'] = (direction * df['volume'].fillna(0)).cumsum()
    df['volume_ma'] = df['volume'].rolling(20).mean()
    return df


def main():
    env = load_env()
    with psycopg.connect(env['DATABASE_URL'], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT stock_code, stock_name FROM kospi_top50 WHERE is_active=true ORDER BY rank")
            stocks = cur.fetchall()
    if not stocks:
        raise RuntimeError('active stocks not found')

    all_rows = []
    insufficient = []
    with psycopg.connect(env['DATABASE_URL'], connect_timeout=20, prepare_threshold=None) as conn:
        for code, name in stocks:
            df = pd.read_sql("""
                SELECT stock_code, date, open, high, low, close, volume
                FROM daily_prices
                WHERE stock_code=%s AND source='kiwoom_ka10081'
                ORDER BY date
            """, conn, params=(code,))
            if len(df) < 60:
                insufficient.append((code, name, len(df)))
                continue
            df['date'] = pd.to_datetime(df['date'])
            ind = calc_indicators(df)
            usable = ind.dropna(subset=['ma_60', 'rsi', 'bb_upper', 'atr']).copy()
            for _, r in usable.iterrows():
                all_rows.append({
                    'stock_code': str(r['stock_code']),
                    'date': r['date'].date().isoformat(),
                    'time_frame': 'daily',
                    'ma_5': float(r['ma_5']) if pd.notna(r['ma_5']) else None,
                    'ma_20': float(r['ma_20']) if pd.notna(r['ma_20']) else None,
                    'ma_60': float(r['ma_60']) if pd.notna(r['ma_60']) else None,
                    'rsi': float(r['rsi']) if pd.notna(r['rsi']) else None,
                    'macd': float(r['macd']) if pd.notna(r['macd']) else None,
                    'signal_line': float(r['signal_line']) if pd.notna(r['signal_line']) else None,
                    'macd_hist': float(r['macd_hist']) if pd.notna(r['macd_hist']) else None,
                    'bb_upper': float(r['bb_upper']) if pd.notna(r['bb_upper']) else None,
                    'bb_middle': float(r['bb_middle']) if pd.notna(r['bb_middle']) else None,
                    'bb_lower': float(r['bb_lower']) if pd.notna(r['bb_lower']) else None,
                    'atr': float(r['atr']) if pd.notna(r['atr']) else None,
                    'obv': int(r['obv']) if pd.notna(r['obv']) else None,
                    'volume_ma': int(r['volume_ma']) if pd.notna(r['volume_ma']) else None,
                })
            print(f"{code} {name}: daily={len(df)}, indicators={len(usable)}")

    if insufficient:
        print('데이터 부족 종목:')
        for item in insufficient:
            print(item)
    if not all_rows:
        raise RuntimeError('no indicators calculated')

    sql = """
        INSERT INTO technical_indicators (
            stock_code, date, time_frame, ma_5, ma_20, ma_60, rsi, macd, signal_line,
            macd_hist, bb_upper, bb_middle, bb_lower, atr, obv, volume_ma, updated_at
        ) VALUES (
            %(stock_code)s, %(date)s, %(time_frame)s, %(ma_5)s, %(ma_20)s, %(ma_60)s,
            %(rsi)s, %(macd)s, %(signal_line)s, %(macd_hist)s, %(bb_upper)s,
            %(bb_middle)s, %(bb_lower)s, %(atr)s, %(obv)s, %(volume_ma)s, NOW()
        )
        ON CONFLICT (stock_code, date, time_frame) DO UPDATE SET
            ma_5=EXCLUDED.ma_5, ma_20=EXCLUDED.ma_20, ma_60=EXCLUDED.ma_60,
            rsi=EXCLUDED.rsi, macd=EXCLUDED.macd, signal_line=EXCLUDED.signal_line,
            macd_hist=EXCLUDED.macd_hist, bb_upper=EXCLUDED.bb_upper,
            bb_middle=EXCLUDED.bb_middle, bb_lower=EXCLUDED.bb_lower, atr=EXCLUDED.atr,
            obv=EXCLUDED.obv, volume_ma=EXCLUDED.volume_ma, updated_at=NOW()
    """
    with psycopg.connect(env['DATABASE_URL'], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, all_rows)
            cur.execute("SELECT COUNT(*), COUNT(DISTINCT stock_code), MIN(date), MAX(date) FROM technical_indicators WHERE time_frame='daily'")
            summary = cur.fetchone()
            cur.execute("""
                SELECT stock_code, COUNT(*), MIN(date), MAX(date)
                FROM technical_indicators
                WHERE time_frame='daily'
                GROUP BY stock_code
                ORDER BY stock_code
                LIMIT 10
            """)
            sample = cur.fetchall()
        conn.commit()
    print('\nDB 검증:')
    print(f'total={summary[0]}, stock_count={summary[1]}, date_range={summary[2]}~{summary[3]}')
    for row in sample:
        print(row)

if __name__ == '__main__':
    main()
