#!/usr/bin/env python3
from pathlib import Path
import pandas as pd
import psycopg
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env'
REPORT_DIR = ROOT / 'reports'

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
    df = pd.read_sql("""
        SELECT date, open, high, low, close, volume
        FROM daily_prices
        WHERE stock_code='005930' AND source='kiwoom_ka10081'
        ORDER BY date
    """, conn)

df['date'] = pd.to_datetime(df['date'])
for c in ['open','high','low','close','volume']:
    df[c] = pd.to_numeric(df[c], errors='coerce')
df['ma5'] = df['close'].rolling(5).mean()
df['ma20'] = df['close'].rolling(20).mean()
df['ma60'] = df['close'].rolling(60).mean()
df['vol_ma20'] = df['volume'].rolling(20).mean()
plot_df = df.tail(220).copy()

REPORT_DIR.mkdir(parents=True, exist_ok=True)
out = REPORT_DIR / 'samsung_validation_static.png'
fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True, gridspec_kw={'height_ratios':[3,1,1]})
ax = axes[0]
ax.plot(plot_df['date'], plot_df['close'], label='Close', color='black', linewidth=1.6)
ax.plot(plot_df['date'], plot_df['ma5'], label='MA5', linewidth=1.1)
ax.plot(plot_df['date'], plot_df['ma20'], label='MA20', linewidth=1.1)
ax.plot(plot_df['date'], plot_df['ma60'], label='MA60', linewidth=1.1)
ax.fill_between(plot_df['date'], plot_df['low'], plot_df['high'], color='gray', alpha=0.15, label='Low~High')
ax.set_title('Samsung Electronics 005930 - Kiwoom Daily Validation (last 220 sessions)')
ax.set_ylabel('Price')
ax.grid(True, alpha=0.25)
ax.legend(loc='upper left', ncol=5)

axes[1].bar(plot_df['date'], plot_df['volume'], color='slategray', alpha=0.75, label='Volume')
axes[1].plot(plot_df['date'], plot_df['vol_ma20'], color='orange', label='Volume MA20')
axes[1].set_ylabel('Volume')
axes[1].grid(True, alpha=0.25)
axes[1].legend(loc='upper left')

ret = plot_df['close'].pct_change() * 100
axes[2].plot(plot_df['date'], ret, color='purple', label='Daily Return %')
axes[2].axhline(0, color='black', linewidth=0.8)
axes[2].set_ylabel('Return %')
axes[2].grid(True, alpha=0.25)
axes[2].legend(loc='upper left')

fig.tight_layout()
fig.savefig(out, dpi=160)
print(out)
