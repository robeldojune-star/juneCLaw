#!/usr/bin/env python3
"""
Backtest RSI(14) strategy with trailing stop.
- Entry: RSI < 30 (oversold)
- Exit: RSI > 70 (overbought) OR trailing stop (5% from peak) OR time exit at 15:20
- Re-entry allowed if new signal and price > previous entry price (to avoid immediate lower re-entry)
- Costs: fee 23bps + slippage 10bps per side (roundtrip 66bps)
- Test on small sample for speed.
"""
import sys
import json
import csv
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from core.fujimoto_126_filter import PriceBar  # just for structure, we'll create our own

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

def fetch_bars_kst_date(sb, stock_code, kst_date):
    start_kst = datetime.combine(kst_date, datetime.min.time())
    end_kst = start_kst + timedelta(days=1)
    start_utc = start_kst - timedelta(hours=9)
    end_utc = end_kst - timedelta(hours=9)
    start_str = start_utc.isoformat()
    end_str = end_utc.isoformat()
    rows = sb.get('intraday_prices', {
        'stock_code': f'eq.{stock_code}',
        'source': f'eq.{SOURCE}',
        'time_frame': f'eq.{TIME_FRAME}',
        'timestamp': f'gte.{start_str}',
        'timestamp': f'lt.{end_str}'
    }, timeout=10)
    bars = []
    for r in rows:
        dt = datetime.fromisoformat(r['timestamp'])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(KST)
        bars.append(PriceBar(
            ts=dt,
            hhmm=dt.strftime('%H:%M'),
            open=float(r['open']),
            high=float(r['high']),
            low=float(r['low']),
            close=float(r['close']),
            volume=int(r['volume'] or 0)
        ))
    bars.sort(key=lambda b: b.ts)
    return bars

def compute_rsi(closes, period=14):
    """Returns list of RSI values aligned with closes (first period-1 are None)."""
    if len(closes) < period:
        return [None] * len(closes)
    rsi = [None] * (period - 1)
    # initial average gain and loss
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
    # subsequent values using Wilder's smoothing
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

def simulate_rsi_trailing(bars, *, rsi_period=14, rsi_entry=30, rsi_exit=70,
                          trailing_percent=0.05, fee_bps=23.0, slippage_bps=10.0):
    if not bars:
        return {"ok": False, "blocking_conditions": ["missing_intraday_bars"]}
    closes = [float(b.close) for b in bars if b.close is not None]
    if len(closes) < rsi_period:
        return {"ok": False, "blocking_conditions": ["not_enough_data_for_rsi"]}
    rsi_vals = compute_rsi(closes, period=rsi_period)
    # align rsi with bars (first rsi_period-1 None)
    in_position = False
    entry_price = 0.0
    entry_dt = None
    remaining = 0.0
    peak_price = 0.0
    trade_chunks = []
    last_exit_price = 0.0
    last_exit_time = None
    original_entry_price_for_reentry = 0.0
    i = 0
    n = len(bars)
    while i < n:
        bar = bars[i]
        rsi = rsi_vals[i] if i < len(rsi_vals) else None
        high = float(bar.high) if bar.high is not None else 0.0
        low = float(bar.low) if bar.low is not None else 0.0
        close = float(bar.close) if bar.close is not None else 0.0
        time_str = bar.hhmm
        cur_dt = bar.ts
        # entry logic
        if not in_position and rsi is not None and rsi < rsi_entry:
            can_enter = True
            if last_exit_price > 0 and original_entry_price_for_reentry > 0:
                if close <= original_entry_price_for_reentry:
                    can_enter = False
            if can_enter:
                in_position = True
                entry_price = close
                entry_dt = cur_dt
                remaining = 1.0
                peak_price = close
                original_entry_price_for_reentry = entry_price
        # exit logic
        if in_position and entry_price > 0 and entry_dt is not None:
            # update peak
            if high > peak_price:
                peak_price = high
            # check RSI exit
            if rsi is not None and rsi > rsi_exit:
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": close,
                    "exit_time": time_str,
                    "reason": "RSI_EXIT",
                    "size": remaining,
                })
                last_exit_price = close
                last_exit_time = cur_dt
                remaining = 0.0
                in_position = False
                i += 1
                continue
            # check trailing stop
            if trailing_percent > 0 and peak_price > 0:
                drawdown = (peak_price - close) / peak_price
                if drawdown >= trailing_percent:
                    trade_chunks.append({
                        "entry_price": entry_price,
                        "entry_time": entry_dt.strftime('%H:%M'),
                        "exit_price": close,
                        "exit_time": time_str,
                        "reason": f"TRAILING_{int(trailing_percent*100)}",
                        "size": remaining,
                    })
                    last_exit_price = close
                    last_exit_time = cur_dt
                    original_entry_price_for_reentry = entry_price
                    remaining = 0.0
                    in_position = False
                    i += 1
                    continue
            # time exit
            if time_str >= "15:20":
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": close,
                    "exit_time": time_str,
                    "reason": "TIME_EXIT",
                    "size": remaining,
                })
                last_exit_price = close
                last_exit_time = cur_dt
                remaining = 0.0
                in_position = False
                i += 1
                continue
        i += 1
    # end of data
    if in_position and remaining > 0 and entry_price > 0:
        close_price = float(bars[-1].close) if bars[-1].close is not None else entry_price
        trade_chunks.append({
            "entry_price": entry_price,
            "entry_time": entry_dt.strftime('%H:%M') if entry_dt else "",
            "exit_price": close_price,
            "exit_time": bars[-1].hhmm,
            "reason": "END_OF_DATA",
            "size": remaining,
        })
        last_exit_price = close_price
        last_exit_time = bars[-1].ts
        remaining = 0.0
        in_position = False
    if not trade_chunks:
        # no trades, return blocked with eval? we can just return ok false
        return {"ok": False, "blocking_conditions": ["no_triggers"]}
    # compute stats
    total_size = sum(tc["size"] for tc in trade_chunks)
    total_cost = 0.0
    total_gross = 0.0
    for tc in trade_chunks:
        entry = tc["entry_price"]
        exitp = tc["exit_price"]
        size = tc["size"]
        if entry > 0:
            gross = (exitp - entry) / entry * 100.0
            total_gross += gross * size
            cost_per_unit = ((fee_bps + slippage_bps) / 100.0) * 2.0
            total_cost += cost_per_unit * size
    if total_size > 0:
        avg_gross = total_gross / total_size
        avg_cost = total_cost / total_size
        net = avg_gross - avg_cost
    else:
        avg_gross = 0.0
        avg_cost = 0.0
        net = 0.0
    signal = "RSI_ENTRY" if trade_chunks else "BLOCKED"
    return {
        "ok": True,
        "strategy": "rsi_14_trailing_v1",
        "entry_time": trade_chunks[0]["entry_time"] if trade_chunks else "",
        "entry_price": round(trade_chunks[0]["entry_price"], 4) if trade_chunks else 0,
        "entry_stage": "UNKNOWN",
        "position_units": 0,
        "entry_score_total": 0.0,
        "entry_score_details": {},
        "exit_time": trade_chunks[-1]["exit_time"] if trade_chunks else "",
        "exit_price": round(trade_chunks[-1]["exit_price"], 4) if trade_chunks else 0,
        "exit_reason": trade_chunks[-1]["reason"] if trade_chunks else "",
        "gross_return_pct": round(avg_gross, 4),
        "cost_pct": round(avg_cost, 4),
        "net_return_pct": round(net, 4),
        "blocking_conditions": [],
        "paper_order_allowed": False,
        "real_order_allowed": False,
        "order_execution_enabled": False,
    }

def main():
    sb = SupabaseRestClient()
    # small sample: first 2 stocks, last 3 days
    stock_codes = KOSPI_TOP_50[:2]
    end_date = datetime.now(KST).date()
    start_date = end_date - timedelta(days=2)  # last 3 days
    dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    print(f"Testing RSI strategy on {len(stock_codes)} stocks from {start_date} to {end_date}")
    # prefetch
    bars_by_stock_date = {}
    fetch_start = time.time()
    for sc in stock_codes:
        print(f"  Fetching {sc}...")
        grouped = {}
        for d in dates:
            bars = fetch_bars_kst_date(sb, sc, d)
            grouped[d] = bars
        bars_by_stock_date[sc] = grouped
    print(f"  Prefetch done in {time.time()-fetch_start:.1f}s")
    # parameters
    params = {
        'rsi_period': 14,
        'rsi_entry': 30,
        'rsi_exit': 70,
        'trailing_percent': 0.05,
        'fee_bps': 23.0,
        'slippage_bps': 10.0,
    }
    results = []
    for sc in stock_codes:
        grouped = bars_by_stock_date[sc]
        current = start_date
        while current <= end_date:
            bars = grouped.get(current, [])
            if not bars:
                current += timedelta(days=1)
                continue
            print(f"  {sc} {current}: {len(bars)} bars")
            trade = simulate_rsi_trailing(bars, **params)
            trade['stock_code'] = sc
            trade['date'] = current.isoformat()
            results.append(trade)
            if trade.get('ok'):
                print(f"    -> OK: entry={trade.get('entry_price')}, exit={trade.get('exit_price')}, reason={trade.get('exit_reason')}, net={trade.get('net_return_pct')}%")
            else:
                print(f"    -> Blocked: {trade.get('blocking_conditions')}")
            current += timedelta(days=1)
    # summary
    print("\n=== Summary ===")
    successful = [r for r in results if r.get('ok')]
    if successful:
        returns = [r['net_return_pct'] for r in successful if r.get('net_return_pct') is not None]
        if returns:
            avg_return = sum(returns) / len(returns)
            positive_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
            print(f"Total days evaluated: {len(results)}")
            print(f"Successful trades: {len(successful)}/{len(results)}")
            print(f"Average net return: {avg_return:.4f}%")
            print(f"Positive rate: {positive_rate:.2f}%")
            print(f"Min return: {min(returns):.4f}%")
            print(f"Max return: {max(returns):.4f}%")
        else:
            print("No returns available.")
    else:
        print("No successful trades.")
    # save
    out_path = Path('/home/june/trading/reports/rsi_14_trailing_backtest.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'stocks': stock_codes,
            'date_range': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'parameters': params,
            'results': results
        }, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")
    elapsed = time.time() - fetch_start
    print(f"Total execution time: {elapsed:.1f}s")

if __name__ == '__main__':
    main()