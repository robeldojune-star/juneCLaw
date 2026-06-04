#!/usr/bin/env python3
"""
Backtest with dynamic exit strategies:
- Intraday moving average exit (20-period, 60-period on 1-minute close)
- Trailing stop (based on peak price since entry)
- Optional: use prior day high/low for exit (requires daily aggregation, skip for now)
- Keep original time exit at 15:20
- Re-entry logic unchanged
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

def simulate_dynamic_exit(bars, *, 
                          stop_loss_pct=-5.0,  # hard stop loss as safety
                          take_profit_pct=10.0,  # first target
                          take_profit_half_pct=20.0,  # second target
                          max_holding_days=3,
                          fee_bps=23.0, slippage_bps=10.0, min_score=60.0,
                          use_ma_exit=True, ma_period=20,  # 20-period SMA on close
                          use_trailing=True, trailing_percent=0.05,  # 5% trailing from peak
                          ):
    """
    Returns dict with trade results.
    """
    if not bars:
        return {"ok": False, "blocking_conditions": ["missing_intraday_bars"]}
    in_position = False
    entry_price = 0.0
    entry_dt = None
    remaining = 0.0
    # hard stop loss price (static)
    stop_loss_price = 0.0
    # target prices (static)
    target_price = 0.0
    target_half_price = 0.0
    # for trailing
    peak_price = 0.0
    # for MA exit: we'll compute SMA on the fly
    # we can keep a list of closes
    close_history = []
    trade_chunks = []
    last_exit_price = 0.0
    last_exit_time = None
    original_entry_price_for_reentry = 0.0
    i = 0
    n = len(bars)
    while i < n:
        bar = bars[i]
        window = bars[: i + 1]
        # update close history for SMA
        close_val = float(bar.close) if bar.close is not None else 0.0
        close_history.append(close_val)
        # compute SMA if enough history
        sma_val = None
        if use_ma_exit and len(close_history) >= ma_period:
            sma_val = sum(close_history[-ma_period:]) / ma_period
        # evaluate signal for entry
        eval_result = evaluate_fujimoto_126(window, min_score=min_score)
        signal = eval_result.get("signal", "")
        if not in_position and signal == "HIGH_CONFIDENCE_CANDIDATE":
            can_enter = True
            if last_exit_price > 0 and original_entry_price_for_reentry > 0 and bar.close is not None:
                if bar.close <= original_entry_price_for_reentry:
                    can_enter = False
            if can_enter:
                in_position = True
                entry_price = float(bar.close) if bar.close is not None else 0.0
                entry_dt = bar.ts
                remaining = 1.0
                stop_loss_price = entry_price * (1.0 + stop_loss_pct / 100.0)
                target_price = entry_price * (1.0 + take_profit_pct / 100.0)
                target_half_price = entry_price * (1.0 + take_profit_half_pct / 100.0)
                peak_price = entry_price
                original_entry_price_for_reentry = entry_price
                # reset history? keep as is
        # exit logic if in position
        if in_position and entry_price > 0 and entry_dt is not None:
            high = float(bar.high) if bar.high is not None else 0.0
            low = float(bar.low) if bar.low is not None else 0.0
            close = float(bar.close) if bar.close is not None else 0.0
            time_str = bar.hhmm
            cur_dt = bar.ts
            # update peak
            if high > peak_price:
                peak_price = high
            # check max holding days
            if remaining > 0:
                days_held = (cur_dt - entry_dt).total_seconds() / (24 * 3600)
                if days_held >= max_holding_days:
                    trade_chunks.append({
                        "entry_price": entry_price,
                        "entry_time": entry_dt.strftime('%H:%M'),
                        "exit_price": close,
                        "exit_time": time_str,
                        "reason": "MAX_HOLDING_DAYS",
                        "size": remaining,
                    })
                    last_exit_price = close
                    last_exit_time = cur_dt
                    remaining = 0.0
                    in_position = False
                    i += 1
                    continue
            # check hard stop loss
            if remaining > 0 and low <= stop_loss_price:
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": stop_loss_price,
                    "exit_time": time_str,
                    "reason": "STOP_LOSS",
                    "size": remaining,
                })
                last_exit_price = stop_loss_price
                last_exit_time = cur_dt
                original_entry_price_for_reentry = entry_price
                remaining = 0.0
                in_position = False
                i += 1
                continue
            # check MA exit (close below SMA)
            if use_ma_exit and sma_val is not None and remaining > 0 and close < sma_val:
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": close,
                    "exit_time": time_str,
                    "reason": f"MA_{ma_period}_EXIT",
                    "size": remaining,
                })
                last_exit_price = close
                last_exit_time = cur_dt
                remaining = 0.0
                in_position = False
                i += 1
                continue
            # check trailing stop
            if use_trailing and remaining > 0 and peak_price > 0:
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
            # check take profit (first half) only if we still have full position
            elif remaining == 1.0 and high >= target_price:
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": target_price,
                    "exit_time": time_str,
                    "reason": "TARGET_HALF",
                    "size": 0.5,
                })
                remaining = 0.5
                stop_loss_price = entry_price  # move to break-even
                target_price = target_half_price
            elif remaining == 0.5 and high >= target_half_price:
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": target_half_price,
                    "exit_time": time_str,
                    "reason": "TARGET_FULL",
                    "size": remaining,
                })
                last_exit_price = target_half_price
                last_exit_time = cur_dt
                remaining = 0.0
                in_position = False
            # time exit (intraday)
            elif time_str >= "15:20":
                exit_price = close if close > 0 else entry_price
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": exit_price,
                    "exit_time": time_str,
                    "reason": "TIME_EXIT",
                    "size": remaining,
                })
                last_exit_price = exit_price
                last_exit_time = cur_dt
                remaining = 0.0
                in_position = False
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
        final_eval = evaluate_fujimoto_126(bars, min_score=min_score)
        return {"ok": False, **final_eval}
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
    signal = "HIGH_CONFIDENCE_CANDIDATE" if trade_chunks else "BLOCKED"
    return {
        "ok": True,
        "strategy": "fujimoto_126_dynamic_exit_v1",
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
    # Test on first 5 stocks, last 3 days
    stock_codes = KOSPI_TOP_50[:5]
    end_date = datetime.now(KST).date()
    start_date = end_date - timedelta(days=2)  # last 3 days
    print(f"Testing dynamic exit on {len(stock_codes)} stocks from {start_date} to {end_date}")
    # Prefetch bars
    bars_by_stock_date = {}
    fetch_start = time.time()
    for sc in stock_codes:
        print(f"  Fetching {sc}...")
        all_bars = fetch_all_bars_for_stock(sb, sc)
        # group by date
        grouped = defaultdict(list)
        for bar in all_bars:
            grouped[bar.ts.date()].append(bar)
        bars_by_stock_date[sc] = grouped
    print(f"  Prefetch done in {time.time()-fetch_start:.1f}s")
    # Parameters to test
    params = {
        'stop_loss_pct': -5.0,
        'take_profit_pct': 10.0,
        'take_profit_half_pct': 20.0,
        'max_holding_days': 3,
        'fee_bps': 23.0,
        'slippage_bps': 10.0,
        'min_score': 60.0,
        'use_ma_exit': True,
        'ma_period': 20,
        'use_trailing': True,
        'trailing_percent': 0.05,
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
            trade = simulate_dynamic_exit(bars, **params)
            trade['stock_code'] = sc
            trade['date'] = current.isoformat()
            results.append(trade)
            if trade.get('ok'):
                print(f"    -> OK: entry={trade.get('entry_price')}, exit={trade.get('exit_price')}, reason={trade.get('exit_reason')}, net={trade.get('net_return_pct')}%")
            else:
                print(f"    -> Blocked: {trade.get('blocking_conditions')}")
            current += timedelta(days=1)
    # Summary
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
    # Save
    out_path = Path('/home/june/trading/reports/dynamic_exit_ma_trailing.json')
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