#!/usr/bin/env python3
"""
Scan KOSPI Top 50 for the same in-sample period (signal 2026-05-28, entry 2026-05-29)
using the strategy from the best backtest (Fujimoto 1-2-6 STAGE3 signal -> enter next day,
exit at take profit +3%, stop loss -2%, time exit 15:20).
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

def simulate_strategy(bars_signal, bars_entry, *, stop_loss_pct=-2.0, take_profit_pct=3.0, max_holding_days=3, fee_bps=23.0, slippage_bps=10.0, min_score=60.0):
    """
    bars_signal: minute bars for signal date (2026-05-28) used to detect STAGE3 signal at any time.
    bars_entry: minute bars for entry date (2026-05-29) used to simulate entry at first bar (open) or at signal time?
    According to the original backtest: signal on date D, entry on next trading date D+1 at the time the signal occurred? Actually from the JSON: signal_date 2026-05-28, entry_trading_date 2026-05-29, entry_time 10:29 etc. So they entered at the same time-of-day as the signal occurred on the previous day? Wait: signal_date is when the signal was detected (based on intraday data up to that day). entry_trading_date is the next day, entry_time is the time of day when they entered (likely at the same clock time as when the signal was triggered? Actually they used the signal time from previous day? Looking at first result: signal_date 2026-05-28, entry_trading_date 2026-05-29, entry_time 10:29, entry_price 717000.0. That suggests they used the signal time (10:29) from the previous day and applied it to the next day's open? Not exactly. Probably they waited until the next day at the same time as the signal occurred (i.e., if signal at 10:29 on 28th, they entered at 10:29 on 29th). We'll adopt that: detect signal time on signal date, then entry at same HH:MM on entry date at the open price of that minute? Actually entry_price equals close of that minute bar? In the data, entry_price equals the close of the minute bar at that time on entry date? Let's assume they entered at the close of the minute bar at that time on entry date.

    We'll implement: detect first time on signal date where evaluate_fujimoto_126 returns STAGE3 signal. Record that time (HH:MM). Then on entry date, find the bar with same HH:MM, enter at its close price. If that bar doesn't exist, skip.

    Exit rules: from entry time onward on entry date, check each minute bar for stop loss, take profit, max holding (3 days), time exit 15:20.
    """
    if not bars_signal or not bars_entry:
        return {"ok": False, "blocking_conditions": ["missing_intraday_bars"]}
    
    # Find signal time on signal date
    signal_time = None
    signal_score = 0.0
    signal_details = {}
    for bar in bars_signal:
        window = [b for b in bars_signal if b.ts <= bar.ts]  # all bars up to and including this bar
        eval_result = evaluate_fujimoto_126(window, min_score=min_score, include_order_blocks=False)
        if eval_result.get("signal") == "HIGH_CONFIDENCE_CANDIDATE":
            signal_time = bar.hhmm
            signal_score = eval_result.get("score_total", 0.0)
            signal_details = eval_result.get("score_details", {})
            break
    
    if signal_time is None:
        return {"ok": False, "blocking_conditions": ["no_signal_on_signal_date"]}
    
    # Find entry bar on entry date with same HH:MM
    entry_bar = None
    for bar in bars_entry:
        if bar.hhmm == signal_time:
            entry_bar = bar
            break
    if entry_bar is None:
        # fallback: use first bar of entry date
        entry_bar = bars_entry[0]
        signal_time = entry_bar.hhmm  # adjust
    
    entry_price = float(entry_bar.close) if entry_bar.close is not None else 0.0
    entry_dt = entry_bar.ts
    
    # Initialize
    in_position = True
    remaining = 1.0
    stop_loss_price = entry_price * (1.0 + stop_loss_pct / 100.0)
    target_price = entry_price * (1.0 + take_profit_pct / 100.0)
    
    trade_chunks = []
    last_exit_price = 0.0
    last_exit_time = None
    
    # Iterate through entry date bars from entry time onward
    start_idx = None
    for idx, bar in enumerate(bars_entry):
        if bar.hhmm == signal_time:
            start_idx = idx
            break
    if start_idx is None:
        start_idx = 0
    
    i = start_idx
    n = len(bars_entry)
    while i < n:
        bar = bars_entry[i]
        high = float(bar.high) if bar.high is not None else 0.0
        low = float(bar.low) if bar.low is not None else 0.0
        close = float(bar.close) if bar.close is not None else 0.0
        time_str = bar.hhmm
        cur_dt = bar.ts
        
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
            
            # Stop loss
            if low <= stop_loss_price:
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
                remaining = 0.0
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
                    "size": remaining,
                })
                last_exit_price = target_price
                last_exit_time = cur_dt
                remaining = 0.0
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
                    "size": remaining,
                })
                last_exit_price = exit_price
                last_exit_time = cur_dt
                remaining = 0.0
                in_position = False
        
        i += 1
    
    # If position still open at end of data
    if in_position and remaining > 0 and entry_price > 0:
        close_price = float(bars_entry[-1].close) if bars_entry[-1].close is not None else entry_price
        trade_chunks.append({
            "entry_price": entry_price,
            "entry_time": entry_dt.strftime('%H:%M') if entry_dt else "",
            "exit_price": close_price,
            "exit_time": bars_entry[-1].hhmm,
            "reason": "END_OF_DATA",
            "size": remaining,
        })
        last_exit_price = close_price
        last_exit_time = bars_entry[-1].ts
        remaining = 0.0
        in_position = False
    
    if not trade_chunks:
        final_eval = evaluate_fujimoto_126(bars_signal, min_score=min_score, include_order_blocks=False)
        return {"ok": False, **final_eval}
    
    # Calculate returns (assuming single chunk, but sum if multiple)
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
    
    return {
        "ok": True,
        "strategy": "fujimoto_126_take_profit_scan",
        "signal_time": signal_time,
        "entry_time": trade_chunks[0]["entry_time"] if trade_chunks else "",
        "entry_price": round(trade_chunks[0]["entry_price"], 4) if trade_chunks else 0,
        "entry_score_total": round(signal_score, 4),
        "entry_score_details": signal_details,
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
    signal_date = datetime(2026, 5, 28, tzinfo=KST).date()
    entry_date = datetime(2026, 5, 29, tzinfo=KST).date()
    
    print(f"Signal date: {signal_date}, Entry date: {entry_date}")
    print(f"Scanning {len(KOSPI_TOP_50)} stocks...")
    
    # Prefetch data for both dates
    bars_signal_by_stock = {}
    bars_entry_by_stock = {}
    fetch_start = time.time()
    for sc in KOSPI_TOP_50:
        print(f"  Fetching {sc}...")
        all_bars = fetch_all_bars_for_stock(sb, sc)
        signal_bars = [b for b in all_bars if b.ts.date() == signal_date]
        entry_bars = [b for b in all_bars if b.ts.date() == entry_date]
        bars_signal_by_stock[sc] = signal_bars
        bars_entry_by_stock[sc] = entry_bars
    print(f"  Prefetch done in {time.time()-fetch_start:.1f}s")
    
    # Parameters
    params = {
        'stop_loss_pct': -2.0,
        'take_profit_pct': 3.0,
        'max_holding_days': 3,
        'fee_bps': 23.0,
        'slippage_bps': 10.0,
        'min_score': 60.0,
    }
    
    results = []
    for sc in KOSPI_TOP_50:
        signal_bars = bars_signal_by_stock[sc]
        entry_bars = bars_entry_by_stock[sc]
        if not signal_bars or not entry_bars:
            print(f"  {sc}: missing data for signal or entry date")
            continue
        print(f"  {sc}: signal bars={len(signal_bars)}, entry bars={len(entry_bars)}")
        trade = simulate_strategy(signal_bars, entry_bars, **params)
        trade['stock_code'] = sc
        results.append(trade)
        
        if trade.get('ok'):
            print(f"    -> OK: entry={trade.get('entry_price')}, exit={trade.get('exit_price')}, reason={trade.get('exit_reason')}, net={trade.get('net_return_pct')}%")
        else:
            print(f"    -> Blocked: {trade.get('blocking_conditions')}")
    
    # Summary
    print("\n=== Scan Summary ===")
    successful = [r for r in results if r.get('ok')]
    if successful:
        returns = [r['net_return_pct'] for r in successful if r.get('net_return_pct') is not None]
        if returns:
            avg_return = sum(returns) / len(returns)
            positive_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
            print(f"Total stocks evaluated: {len(results)}")
            print(f"Successful trades: {len(successful)}/{len(results)}")
            print(f"Average net return: {avg_return:.4f}%")
            print(f"Positive rate: {positive_rate:.2f}%")
            print(f"Min return: {min(returns):.4f}%")
            print(f"Max return: {max(returns):.4f}%")
            
            # Show some details
            print("\n--- Sample of successful trades ---")
            for r in successful[:5]:
                print(f"{r['stock_code']}: entry {r['entry_price']} -> exit {r['exit_price']} ({r['exit_reason']}) net {r['net_return_pct']}%")
        else:
            print("No returns available.")
    else:
        print("No successful trades.")
    
    # Save results
    out_path = Path('/home/june/trading/reports/fujimoto_126_take_profit_scan_kospi50.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'signal_date': signal_date.isoformat(),
            'entry_date': entry_date.isoformat(),
            'stocks': KOSPI_TOP_50,
            'parameters': params,
            'results': results
        }, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")
    elapsed = time.time() - fetch_start
    print(f"Total execution time: {elapsed:.1f}s")

if __name__ == '__main__':
    main()