#!/usr/bin/env python3
from pathlib import Path
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

env = load_env()
with psycopg.connect(env['DATABASE_URL'], connect_timeout=20, prepare_threshold=None) as conn:
    with conn.cursor() as cur:
        cur.execute('''
            SELECT COUNT(*), MIN(date), MAX(date), MIN(low), MAX(high), MIN(volume), MAX(volume)
            FROM daily_prices
            WHERE stock_code='005930' AND source='kiwoom_ka10081'
        ''')
        row = cur.fetchone()
        print('삼성전자 일봉 요약')
        print(f'rows={row[0]}, date_range={row[1]}~{row[2]}')
        print(f'price_range_low_high={row[3]}~{row[4]}, volume_range={row[5]}~{row[6]}')
        cur.execute('''
            SELECT date, open, high, low, close, volume
            FROM daily_prices
            WHERE stock_code='005930' AND source='kiwoom_ka10081'
            ORDER BY date DESC
            LIMIT 5
        ''')
        print('최근 5개')
        for r in cur.fetchall():
            print(r)
