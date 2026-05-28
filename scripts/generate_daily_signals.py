#!/usr/bin/env python3
"""Generate latest daily BUY/SELL/HOLD signals from technical_indicators.

Uses 100-point score details. No fake data.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import psycopg

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env'
STRATEGY = 'technical_score_v1'
BUY_THRESHOLD = 60
SELL_THRESHOLD = 30


def load_env():
    env = {}
    for raw in ENV_PATH.read_text(encoding='utf-8', errors='replace').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        env[k.strip()] = v.split(' #', 1)[0].strip().strip('"').strip("'")
    return env


def f(x):
    return float(x) if x is not None else None


def score_signal(row: dict[str, Any], prev: dict[str, Any] | None) -> tuple[str, float, dict[str, Any], str]:
    close = f(row['close']); volume = f(row['volume'])
    ma5 = f(row['ma_5']); ma20 = f(row['ma_20']); ma60 = f(row['ma_60'])
    rsi = f(row['rsi']); macd = f(row['macd']); signal_line = f(row['signal_line']); hist = f(row['macd_hist'])
    bb_upper = f(row['bb_upper']); bb_middle = f(row['bb_middle']); bb_lower = f(row['bb_lower'])
    volume_ma = f(row['volume_ma'])
    prev_close = f(prev['close']) if prev else None
    prev_hist = f(prev['macd_hist']) if prev else None
    ret = ((close / prev_close - 1) * 100) if close and prev_close else None

    details: dict[str, Any] = {'weights': {'trend':35, 'momentum':25, 'macd':20, 'volume':10, 'volatility':5, 'price_change':5}}
    reasons = []

    if ma5 and ma20 and ma60 and close:
        if ma5 > ma20 > ma60 and close > ma5:
            trend = 35; reasons.append('완전 상승 배열 및 종가 MA5 상회')
        elif ma5 > ma20 > ma60:
            trend = 30; reasons.append('완전 상승 배열')
        elif ma5 > ma20 and close > ma20:
            trend = 25; reasons.append('단기 상승 추세')
        elif close > ma60 and ma20 > ma60:
            trend = 20; reasons.append('중기 상승권')
        elif ma5 < ma20 < ma60:
            trend = 0; reasons.append('완전 하락 배열')
        else:
            trend = 12; reasons.append('추세 혼조')
    else:
        trend = 0; reasons.append('추세 지표 부족')

    if rsi is not None:
        if 45 <= rsi <= 65:
            momentum = 25; reasons.append('RSI 안정 상승 구간')
        elif 35 <= rsi < 45:
            momentum = 20; reasons.append('RSI 반등 후보')
        elif 65 < rsi <= 75:
            momentum = 14; reasons.append('RSI 과열 진입')
        elif 25 <= rsi < 35:
            momentum = 12; reasons.append('RSI 과매도권')
        elif rsi > 75:
            momentum = 5; reasons.append('RSI 과열')
        else:
            momentum = 8; reasons.append('RSI 약세')
    else:
        momentum = 0; reasons.append('RSI 부족')

    if macd is not None and signal_line is not None and hist is not None:
        if macd > signal_line and hist > 0 and (prev_hist is None or hist >= prev_hist):
            macd_score = 20; reasons.append('MACD 상승 및 히스토그램 개선')
        elif macd > signal_line and hist > 0:
            macd_score = 16; reasons.append('MACD 상승')
        elif hist > 0:
            macd_score = 10; reasons.append('MACD 히스토그램 양수')
        elif prev_hist is not None and hist > prev_hist:
            macd_score = 7; reasons.append('MACD 약세 완화')
        else:
            macd_score = 0; reasons.append('MACD 약세')
    else:
        macd_score = 0; reasons.append('MACD 부족')

    if volume and volume_ma:
        ratio = volume / volume_ma if volume_ma else None
        if ratio >= 1.5:
            volume_score = 10; reasons.append('거래량 강한 증가')
        elif ratio >= 1.1:
            volume_score = 7; reasons.append('거래량 증가')
        elif ratio >= 0.8:
            volume_score = 5; reasons.append('거래량 보통')
        else:
            volume_score = 2; reasons.append('거래량 부족')
    else:
        ratio = None; volume_score = 0; reasons.append('거래량 지표 부족')

    if close and bb_upper and bb_middle and bb_lower:
        if bb_lower <= close <= bb_middle:
            volatility = 5; reasons.append('볼린저 하단~중단: 부담 낮음')
        elif bb_middle < close <= bb_upper:
            volatility = 3; reasons.append('볼린저 중단~상단')
        elif close < bb_lower:
            volatility = 4; reasons.append('볼린저 하단 이탈: 반등 후보')
        else:
            volatility = 1; reasons.append('볼린저 상단 돌파: 과열 주의')
    else:
        volatility = 0; reasons.append('볼린저 지표 부족')

    if ret is not None:
        if 0 <= ret <= 5:
            price_change = 5; reasons.append('당일 양호한 상승')
        elif -3 <= ret < 0:
            price_change = 3; reasons.append('당일 약한 조정')
        elif 5 < ret <= 10:
            price_change = 2; reasons.append('당일 급등 부담')
        elif ret < -5:
            price_change = 0; reasons.append('당일 급락')
        else:
            price_change = 1; reasons.append('당일 변동 부담')
    else:
        price_change = 0; reasons.append('전일 대비 계산 불가')

    total = trend + momentum + macd_score + volume_score + volatility + price_change
    if total >= BUY_THRESHOLD:
        signal = 'BUY'
    elif total <= SELL_THRESHOLD:
        signal = 'SELL'
    else:
        signal = 'HOLD'

    details.update({
        'trend': trend,
        'momentum': momentum,
        'macd': macd_score,
        'volume': volume_score,
        'volatility': volatility,
        'price_change': price_change,
        'total': total,
        'rsi': rsi,
        'volume_ratio': ratio,
        'daily_return_pct': ret,
        'thresholds': {'BUY': BUY_THRESHOLD, 'SELL': SELL_THRESHOLD},
        'reasons': reasons,
    })
    reason = '; '.join(reasons[:6])
    return signal, total, details, reason


def main():
    env = load_env()
    with psycopg.connect(env['DATABASE_URL'], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(date) FROM technical_indicators WHERE time_frame='daily'")
            target_date = cur.fetchone()[0]
            if not target_date:
                raise RuntimeError('technical_indicators empty')
            cur.execute("""
                SELECT k.rank, k.stock_code, k.stock_name, d.close, d.volume,
                       i.ma_5, i.ma_20, i.ma_60, i.rsi, i.macd, i.signal_line, i.macd_hist,
                       i.bb_upper, i.bb_middle, i.bb_lower, i.atr, i.volume_ma
                FROM kospi_top50 k
                JOIN daily_prices d ON d.stock_code=k.stock_code AND d.date=%s
                JOIN technical_indicators i ON i.stock_code=k.stock_code AND i.date=%s AND i.time_frame='daily'
                WHERE k.is_active=true
                ORDER BY k.rank
            """, (target_date, target_date))
            cols = [desc[0] for desc in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            cur.execute("""
                SELECT d.stock_code, d.close, i.macd_hist
                FROM daily_prices d
                LEFT JOIN technical_indicators i ON i.stock_code=d.stock_code AND i.date=d.date AND i.time_frame='daily'
                WHERE d.date = (SELECT MAX(date) FROM daily_prices WHERE date < %s)
            """, (target_date,))
            prev = {r[0]: {'close': r[1], 'macd_hist': r[2]} for r in cur.fetchall()}
    if len(rows) != 50:
        print(f'⚠️ 대상 종목 수가 50이 아님: {len(rows)}')

    signal_rows = []
    for r in rows:
        sig, score, details, reason = score_signal(r, prev.get(r['stock_code']))
        signal_rows.append({
            'stock_code': r['stock_code'],
            'signal_type': sig,
            'signal_date': f'{target_date} 15:30:00+09',
            'time_frame': 'daily',
            'price': float(r['close']),
            'price_at_signal': float(r['close']),
            'score': score,
            'signal_strength': score,
            'score_details': json.dumps(details, ensure_ascii=False),
            'reason': reason,
            'strategy': STRATEGY,
        })

    sql = """
        INSERT INTO trading_signals (
            stock_code, signal_type, signal_date, time_frame, price, price_at_signal,
            score, signal_strength, score_details, reason, strategy, executed
        ) VALUES (
            %(stock_code)s, %(signal_type)s, %(signal_date)s, %(time_frame)s, %(price)s,
            %(price_at_signal)s, %(score)s, %(signal_strength)s, %(score_details)s::jsonb,
            %(reason)s, %(strategy)s, false
        )
    """
    with psycopg.connect(env['DATABASE_URL'], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM trading_signals WHERE strategy=%s AND signal_date::date=%s", (STRATEGY, target_date))
            cur.executemany(sql, signal_rows)
            cur.execute("""
                SELECT signal_type, COUNT(*), ROUND(AVG(score), 2), MIN(score), MAX(score)
                FROM trading_signals
                WHERE strategy=%s AND signal_date::date=%s
                GROUP BY signal_type
                ORDER BY signal_type
            """, (STRATEGY, target_date))
            summary = cur.fetchall()
            cur.execute("""
                SELECT t.stock_code, k.stock_name, t.signal_type, t.score, t.price, t.reason
                FROM trading_signals t
                LEFT JOIN kospi_top50 k ON k.stock_code=t.stock_code
                WHERE t.strategy=%s AND t.signal_date::date=%s
                ORDER BY t.score DESC
                LIMIT 15
            """, (STRATEGY, target_date))
            top = cur.fetchall()
        conn.commit()

    print(f'신호 생성 완료: target_date={target_date}, rows={len(signal_rows)}, strategy={STRATEGY}')
    print('분포:')
    for row in summary:
        print(row)
    print('상위 15개:')
    for row in top:
        print(row)

if __name__ == '__main__':
    main()
