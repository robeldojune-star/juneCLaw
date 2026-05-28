#!/usr/bin/env python3
from pathlib import Path
import json
import psycopg

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
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT stock_code), MIN(date), MAX(date) FROM technical_indicators WHERE time_frame='daily'")
        ind_summary = cur.fetchone()
        cur.execute("""
            SELECT signal_type, COUNT(*), ROUND(AVG(score), 2), MIN(score), MAX(score)
            FROM trading_signals
            WHERE strategy='technical_score_v1' AND signal_date::date=(SELECT MAX(signal_date::date) FROM trading_signals WHERE strategy='technical_score_v1')
            GROUP BY signal_type
            ORDER BY signal_type
        """)
        signal_summary = cur.fetchall()
        cur.execute("""
            SELECT t.signal_date::date, t.stock_code, k.stock_name, t.signal_type, t.score, t.price, t.score_details, t.reason
            FROM trading_signals t
            LEFT JOIN kospi_top50 k ON k.stock_code=t.stock_code
            WHERE t.strategy='technical_score_v1' AND t.stock_code='005930'
            ORDER BY t.signal_date DESC
            LIMIT 1
        """)
        samsung = cur.fetchone()
        cur.execute("""
            SELECT t.stock_code, k.stock_name, t.signal_type, t.score, t.price
            FROM trading_signals t
            LEFT JOIN kospi_top50 k ON k.stock_code=t.stock_code
            WHERE t.strategy='technical_score_v1' AND t.signal_date::date=(SELECT MAX(signal_date::date) FROM trading_signals WHERE strategy='technical_score_v1')
            ORDER BY t.score DESC
            LIMIT 10
        """)
        top10 = cur.fetchall()

REPORT_DIR.mkdir(parents=True, exist_ok=True)
report = REPORT_DIR / 'pipeline_validation_summary.md'
lines = []
lines.append('# 검증 및 신호 생성 종합 요약')
lines.append('')
lines.append('## 1. 삼성전자 데이터 검증')
lines.append('- 데이터 품질: 통과')
lines.append('- 외부 KRX 비교: 통과, 600개 겹치는 일자 종가 ratio=1.0')
lines.append('- 가격 스케일/수정주가 문제: 현재 DB와 KRX 기준 불일치 없음')
lines.append('- HTML 대시보드: `/home/june/trading/reports/samsung_validation_dashboard.html`')
lines.append('- 정적 PNG: `/home/june/trading/reports/samsung_validation_static.png`')
lines.append('- 리포트: `/home/june/trading/reports/samsung_validation_report.md`')
lines.append('')
lines.append('## 2. 50종목 기술적 지표 계산')
lines.append(f'- rows: `{ind_summary[0]}`')
lines.append(f'- stock_count: `{ind_summary[1]}`')
lines.append(f'- date_range: `{ind_summary[2]} ~ {ind_summary[3]}`')
lines.append('')
lines.append('## 3. 최신 신호 생성 결과')
for sig, cnt, avg, mn, mx in signal_summary:
    lines.append(f'- {sig}: {cnt}개, avg_score={avg}, min={mn}, max={mx}')
lines.append('')
lines.append('## 4. 삼성전자 최신 신호')
if samsung:
    sdate, code, name, sig, score, price, details, reason = samsung
    lines.append(f'- date: `{sdate}`')
    lines.append(f'- stock: `{code} {name}`')
    lines.append(f'- signal: **{sig}**')
    lines.append(f'- score: `{score}`')
    lines.append(f'- price: `{price}`')
    lines.append(f'- reason: {reason}')
    if isinstance(details, str):
        details_obj = json.loads(details)
    else:
        details_obj = details
    lines.append('')
    lines.append('### 삼성전자 점수 세부')
    for k in ['trend','momentum','macd','volume','volatility','price_change','total','rsi','volume_ratio','daily_return_pct']:
        lines.append(f'- {k}: `{details_obj.get(k)}`')
lines.append('')
lines.append('## 5. 상위 점수 TOP10')
lines.append('| code | name | signal | score | price |')
lines.append('|---|---:|---:|---:|---:|')
for code, name, sig, score, price in top10:
    lines.append(f'| {code} | {name} | {sig} | {score} | {price} |')
lines.append('')
lines.append('## 6. 신호 검증 차트')
lines.append('- 삼성전자 신호 오버레이 차트: `/home/june/trading/reports/samsung_signal_validation.html`')
report.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(report)
