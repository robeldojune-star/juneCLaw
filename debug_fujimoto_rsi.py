#!/usr/bin/env python3
"""
Debug script: compute Fujimoto score and RSI for each bar for given stocks/dates.
Print when conditions are close to triggering entry.
"""
import sys
import json
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from collections import defaultdict

sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from core.fujimoto_126_filter import PriceBar, evaluate_fujimoto_126

KST = timezone(timedelta(hours=9))
SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"

def load_kospi_top50(csv_path='/home/june/trading/data/kospi_top50_common_stocks_marketcap_naver.csv'):
    codes = []
    try:
        with open(csv_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get('종목코드')
                if code:
                    codes.append(code.strip())
    except Exception as e:
        print(f"Failed to load KOSPI Top 50 list: {e}")
        codes = []
    seen = set()
    deduped = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped

KOSPI_TOP_50 = load_kospi_top50()
print(f"Loaded {len(KOSPI_TOP_50)} stocks from KOSPI Top 50 list.")

def ts_to_kst(value):
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)

def fetch_all_bars_for_stock(sb, stock_code):
    rows = sb.get('intraday_prices', {
        'stock_code': f'eq.{stock_code}',
        'source': f'eq.{SOURCE}',
        'time_frame': f'eq.{TIME_FRAME}'
    }, timeout=30)
    bars = []
    for row in rows:
        ts = row['timestamp']
        dt = ts_to_kst(ts)
        bars.append(PriceBar(
            ts=dt,
            hhmm=dt.strftime('%H:%M'),
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=int(row['volume'] or 0)
        ))
    bars.sort(key=lambda b: b.ts)
    return bars

def compute_rsi(closes, period=14):
    """Return list of RSI values aligned with closes (first period-1 are None)."""
    if len(closes) < period:
        return [None] * len(closes)
    rsi = [None] * (period - 1)
    gains = []
    losses = []
    for i in range(1, period):
        change = closes[i] - closes[i-1]
        if change >= 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-change)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        rsi.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi.append(100.0 - (100.0 / (1.0 + rs)))
    for i in range(period, len(closes)):
        change = closes[i] - closes[i-1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rsi_val = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_val = 100.0 - (100.0 / (1.0 + rs))
        rsi.append(rsi_val)
    return rsi

def debug_stock(sb, stock_code, start_date, end_date):
    print(f"\n=== Debugging {stock_code} from {start_date} to {end_date} ===")
    all_bars = fetch_all_bars_for_stock(sb, stock_code)
    if not all_bars:
        print("  No bars fetched.")
        return
    grouped = defaultdict(list)
    for bar in all_bars:
        grouped[bar.ts.date()].append(bar)
    closes = [float(b.close) for b in all_bars if b.close is not None]
    rsi_vals = compute_rsi(closes, period=14)
    # map each bar to its rsi
    bar_to_rsi = {}
    for idx, bar in enumerate(all_bars):
        if idx < len(rsi_vals):
            bar_to_rsi[bar] = rsi_vals[idx]
        else:
            bar_to_rsi[bar] = None
    current = start_date
    while current <= end_date:
        bars = grouped.get(current, [])
        if not bars:
            current += timedelta(days=1)
            continue
        print(f"\n  Date {current}: {len(bars)} bars")
        # Show first few bars and any bar where conditions near trigger
        for i, bar in enumerate(bars[:10]):  # first 10 bars
            window = all_bars[: all_bars.index(bar) + 1]
            eval_result = evaluate_fujimoto_126(window, min_score=0)  # get score
            signal = eval_result.get("signal", "")
            score = eval_result.get("score", 0.0)
            details = eval_result.get("details", {})
            rsi = bar_to_rsi.get(bar)
            print(f"    {bar.hhmm} close={bar.close:.0f} score={score:.1f} signal={signal} RSI={rsi:.1f if rsi is not None else 'N/A'}")
            if score >= 40 and (rsi is not None and rsi <= 40):
                print(f"      >>> Near trigger: score≥40 and RSI≤40")
        current += timedelta(days=1)

def main():
    sb = SupabaseRestClient()
    stock_codes = KOSPI_TOP_50[:2]
    end_date = datetime.now(KST).date()
    start_date = end_date - timedelta(days=2)
    for sc in stock_codes:
        debug_stock(sb, sc, start_date, end_date)

if __name__ == '__main__':
    main()