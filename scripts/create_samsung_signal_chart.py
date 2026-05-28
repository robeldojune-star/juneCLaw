#!/usr/bin/env python3
from pathlib import Path
import json
import pandas as pd
import psycopg
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
    prices = pd.read_sql("""
        SELECT d.date, d.open, d.high, d.low, d.close, d.volume,
               i.ma_5, i.ma_20, i.ma_60, i.rsi, i.macd, i.signal_line, i.macd_hist
        FROM daily_prices d
        LEFT JOIN technical_indicators i ON i.stock_code=d.stock_code AND i.date=d.date AND i.time_frame='daily'
        WHERE d.stock_code='005930' AND d.source='kiwoom_ka10081'
        ORDER BY d.date
    """, conn)
    sigs = pd.read_sql("""
        SELECT signal_date, signal_type, score, price, score_details, reason
        FROM trading_signals
        WHERE stock_code='005930' AND strategy='technical_score_v1'
        ORDER BY signal_date
    """, conn)

prices['date'] = pd.to_datetime(prices['date'])
for c in ['open','high','low','close','volume','ma_5','ma_20','ma_60','rsi','macd','signal_line','macd_hist']:
    prices[c] = pd.to_numeric(prices[c], errors='coerce')
plot_df = prices.tail(220).copy()

REPORT_DIR.mkdir(parents=True, exist_ok=True)
fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.52,0.17,0.16,0.15], subplot_titles=('삼성전자 가격 + 최신 신호', '거래량', 'RSI14', 'MACD'))
fig.add_trace(go.Candlestick(x=plot_df['date'], open=plot_df['open'], high=plot_df['high'], low=plot_df['low'], close=plot_df['close'], name='OHLC'), row=1, col=1)
for col, color in [('ma_5','#f59e0b'), ('ma_20','#2563eb'), ('ma_60','#7c3aed')]:
    fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df[col], name=col.upper(), mode='lines', line=dict(color=color, width=1.4)), row=1, col=1)
if not sigs.empty:
    sigs['signal_date'] = pd.to_datetime(sigs['signal_date']).dt.tz_localize(None).dt.normalize()
    latest = sigs.iloc[-1]
    color = {'BUY':'#16a34a','SELL':'#dc2626','HOLD':'#64748b'}.get(latest['signal_type'], '#64748b')
    symbol = {'BUY':'triangle-up','SELL':'triangle-down','HOLD':'circle'}.get(latest['signal_type'], 'circle')
    fig.add_trace(go.Scatter(
        x=[latest['signal_date']], y=[float(latest['price'])], mode='markers+text', name='Latest Signal',
        marker=dict(size=18, color=color, symbol=symbol, line=dict(color='white', width=2)),
        text=[f"{latest['signal_type']} {float(latest['score']):.0f}"], textposition='top center',
        hovertext=[latest['reason']], hoverinfo='text'
    ), row=1, col=1)
fig.add_trace(go.Bar(x=plot_df['date'], y=plot_df['volume'], name='Volume', marker_color='#64748b'), row=2, col=1)
fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df['rsi'], name='RSI', mode='lines', line=dict(color='#0ea5e9')), row=3, col=1)
fig.add_hline(y=70, line_dash='dot', line_color='#ef4444', row=3, col=1)
fig.add_hline(y=30, line_dash='dot', line_color='#22c55e', row=3, col=1)
fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df['macd'], name='MACD', mode='lines', line=dict(color='#2563eb')), row=4, col=1)
fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df['signal_line'], name='Signal', mode='lines', line=dict(color='#f97316')), row=4, col=1)
fig.add_trace(go.Bar(x=plot_df['date'], y=plot_df['macd_hist'], name='Hist', marker_color='#94a3b8'), row=4, col=1)
fig.update_layout(template='plotly_white', title='삼성전자 005930 신호 검증 차트 - technical_score_v1', height=1000, xaxis_rangeslider_visible=False)
out = REPORT_DIR / 'samsung_signal_validation.html'
fig.write_html(out, include_plotlyjs='cdn')
print(out)
if not sigs.empty:
    latest = sigs.iloc[-1]
    print(f"latest_signal={latest['signal_type']}, score={latest['score']}, price={latest['price']}, date={latest['signal_date'].date()}")
    try:
        details = latest['score_details'] if isinstance(latest['score_details'], dict) else json.loads(latest['score_details'])
        print(json.dumps(details, ensure_ascii=False, indent=2)[:1200])
    except Exception as e:
        print(f'details_parse_error={e}')
