#!/usr/bin/env python3
"""
Out-of-sample test of the Fujimoto 1-2-6 + take profit strategy 
on a different period (previous month) to validate robustness.
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

def simulate_take_profit_strategy(bars, *, stop_loss_pct=-2.0, take_profit_pct=3.0, max_holding_days=3, fee_bps=23.0, slippage_bps=10.0, min_score=60.0):
    """Simple strategy: enter on FIRST Fujimoto STAGE3 signal, exit at take profit, stop loss, or time exit."""
    if not bars:
        return {"ok": False, "blocking_conditions": ["missing_intraday_bars"]}
    
    in_position = False
    entry_price = 0.0
    entry_dt = None
    entry_score = 0.0
    entry_details = {}
    stop_loss_price = 0.0
    target_price = 0.0
    trade_chunks = []
    last_exit_price = 0.0
    last_exit_time = None
    i = 0
    n = len(bars)
    
    while i < n:
        bar = bars[i]
        window = bars[: i + 1]
        eval_result = evaluate_fujimoto_126(window, min_score=min_score, include_order_blocks=False)
        signal = eval_result.get("signal", "")
        score_total = eval_result.get("score_total", 0.0)
        
        # Enter on first STAGE3 signal
        if not in_position and signal == "HIGH_CONFIDENCE_CANDIDATE":
            in_position = True
            entry_price = float(bar.close) if bar.close is not None else 0.0
            entry_dt = bar.ts
            entry_score = score_total
            entry_details = eval_result.get("score_details", {})
            stop_loss_price = entry_price * (1.0 + stop_loss_pct / 100.0)
            target_price = entry_price * (1.0 + take_profit_pct / 100.0)
        
        # Check exit conditions if in position
        if in_position and entry_price > 0 and entry_dt is not None:
            high = float(bar.high) if bar.high is not None else 0.0
            low = float(bar.low) if bar.low is not None else 0.0
            close = float(bar.close) if bar.close is not None else 0.0
            time_str = bar.hhmm
            cur_dt = bar.ts
            
            # Max holding period check
            days_held = (cur_dt - entry_dt).total_seconds() / (24 * 3600)
            if days_held >= max_holding_days:
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": close,
                    "exit_time": time_str,
                    "reason": "MAX_HOLDING_DAYS",
                    "size": 1.0,
                })
                last_exit_price = close
                last_exit_time = cur_dt
                in_position = False
                i += 1
                continue
            
            # Stop loss
            if low <= stop_loss_price:
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": stop_loss_price,
                    "exit_time": time_str,
                    "reason": "STOP_LOSS",
                    "size": 1.0,
                })
                last_exit_price = stop_loss_price
                last_exit_time = cur_dt
                in_position = False
                i += 1
                continue
            
            # Take profit
            elif high >= target_price:
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": target_price,
                    "exit_time": time_str,
                    "reason": "TAKE_PROFIT",
                    "size": 1.0,
                })
                last_exit_price = target_price
                last_exit_time = cur_dt
                in_position = False
            
            # Time exit (15:20 KST)
            elif time_str >= "15:20":
                exit_price = close if close > 0 else entry_price
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": exit_price,
                    "exit_time": time_str,
                    "reason": "TIME_EXIT",
                    "size": 1.0,
                })
                last_exit_price = exit_price
                last_exit_time = cur_dt
                in_position = False
        
        i += 1
    
    # Handle any open position at end of data
    if in_position and entry_price > 0:
        close_price = float(bars[-1].close) if bars[-1].close is not None else entry_price
        trade_chunks.append({
            "entry_price": entry_price,
            "entry_time": entry_dt.strftime('%H:%M') if entry_dt else "",
            "exit_price": close_price,
            "exit_time": bars[-1].hhmm,
            "reason": "END_OF_DATA",
            "size": 1.0,
        })
    
    if not trade_chunks:
        final_eval = evaluate_fujimoto_126(bars, min_score=min_score, include_order_blocks=False)
        return {"ok": False, **final_eval}
    
    # Calculate returns (only first trade for simplicity, or average if multiple)
    # For this strategy, we expect at most one trade per day (first signal triggers entry)
    tc = trade_chunks[0]  # Take first trade
    entry = tc["entry_price"]
    exitp = tc["exit_price"]
    if entry > 0:
        gross = (exitp - entry) / entry * 100.0
        cost_per_unit = ((fee_bps + slippage_bps) / 100.0) * 2.0
        net = gross - cost_per_unit
    else:
        gross = 0.0
        cost_per_unit = 0.0
        net = 0.0
    
    return {
        "ok": True,
        "strategy": "fujimoto_126_take_profit_oos",
        "entry_time": tc["entry_time"],
        "entry_price": round(tc["entry_price"], 4),
        "entry_stage": tc.get("entry_stage", "UNKNOWN"),
        "entry_score_total": round(entry_score, 4),
        "entry_score_details": entry_details,
        "exit_time": tc["exit_time"],
        "exit_price": round(tc["exit_price"], 4),
        "exit_reason": tc["reason"],
        "gross_return_pct": round(gross, 4),
        "cost_pct": round(cost_per_unit, 4),
        "net_return_pct": round(net, 4),
        "blocking_conditions": [],
        "paper_order_allowed": False,
        "real_order_allowed": False,
        "order_execution_enabled": False,
    }

def main():
    sb = SupabaseRestClient()
    
    # Test period: 1 month before the original test period
    # Original test was on 2026-05-28 (signal) -> 2026-05-29 (entry)
    # Let's test on 2026-04-28 (signal) -> 2026-04-29 (entry) approximately
    end_date = datetime(2026, 4, 30, tzinfo=KST).date()  # End of April
    start_date = end_date - timedelta(days=20)  # ~20 trading days earlier
    
    print(f"Testing out-of-sample period: {start_date} to {end_date}")
    
    # Test on first 10 stocks for speed
    stock_codes = KOSPI_TOP_50[:10]
    print(f"Testing on {len(stock_codes)} stocks: {stock_codes}")
    
    # Prefetch data
    bars_by_stock_date = {}
    fetch_start = time.time()
    for sc in stock_codes:
        print(f"  Fetching {sc}...")
        all_bars = fetch_all_bars_for_stock(sb, sc)
        grouped = defaultdict(list)
        for bar in all_bars:
            if start_date <= bar.ts.date() <= end_date:
                grouped[bar.ts.date()].append(bar)
        bars_by_stock_date[sc] = grouped
    print(f"  Prefetch done in {time.time()-fetch_start:.1f}s")
    
    # Parameters matching the successful backtest
    params = {
        'stop_loss_pct': -2.0,
        'take_profit_pct': 3.0,
        'max_holding_days': 3,
        'fee_bps': 23.0,
        'slippage_bps': 10.0,
        'min_score': 60.0,
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
            trade = simulate_take_profit_strategy(bars, **params)
            trade['stock_code'] = sc
            trade['date'] = current.isoformat()
            results.append(trade)
            
            if trade.get('ok'):
                print(f"    -> OK: entry={trade.get('entry_price')}, exit={trade.get('exit_price')}, reason={trade.get('exit_reason')}, net={trade.get('net_return_pct')}%")
            else:
                print(f"    -> Blocked: {trade.get('blocking_conditions')}")
            
            current += timedelta(days=1)
    
    # Summary
    print("\n=== Out-of-Sample Summary ===")
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
            
            # Compare to in-sample result
            print(f"\n=== Comparison to In-Sample ===")
            print(f"In-sample avg return: +0.4969% (23 trades, 60.87% win rate)")
            print(f"Out-of-sample avg return: {avg_return:+.4f}% ({len(successful)} trades, {positive_rate:.2f}% win rate)")
        else:
            print("No returns available.")
    else:
        print("No successful trades.")
    
    # Save results
    out_path = Path('/home/june/trading/reports/fujimoto_126_take_profit_oos_test.json')
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