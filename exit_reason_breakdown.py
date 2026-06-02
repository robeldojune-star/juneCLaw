#!/usr/bin/env python3
"""
Detailed exit reason breakdown for SL=-4%, TP=5% on signal date 2026-05-28, entry 2026-05-29.
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

def simulate_strategy(bars_signal, bars_entry, *, stop_loss_pct=-4.0, take_profit_pct=5.0, max_holding_days=3, fee_bps=23.0, slippage_bps=10.0, min_score=60.0):
    if not bars_signal or not bars_entry:
        return {"ok": False, "blocking_conditions": ["missing_intraday_bars"]}
    
    # Find signal time on signal date
    signal_time = None
    signal_score = 0.0
    signal_details = {}
    for bar in bars_signal:
        window = [b for b in bars_signal if b.ts <= bar.ts]
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
        entry_bar = bars_entry[0]
        signal_time = entry_bar.hhmm
    
    entry_price = float(entry_bar.close) if entry_bar.close is not None else 0.0
    entry_dt = entry_bar.ts
    
    in_position = True
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
        
        if in_position:
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
    
    if in_position and entry_price > 0:
        close_price = float(bars_entry[-1].close) if bars_entry[-1].close is not None else entry_price
        trade_chunks.append({
            "entry_price": entry_price,
            "entry_time": entry_dt.strftime('%H:%M') if entry_dt else "",
            "exit_price": close_price,
            "exit_time": bars_entry[-1].hhmm,
            "reason": "END_OF_DATA",
            "size": 1.0,
        })
    
    if not trade_chunks:
        final_eval = evaluate_fujimoto_126(bars_signal, min_score=min_score, include_order_blocks=False)
        return {"ok": False, **final_eval}
    
    # Calculate returns
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
    
    win = 1 if net > 0 else 0
    return {
        "ok": True,
        "net_return_pct": round(net, 4),
        "win": win,
        "exit_reason": trade_chunks[-1]["reason"] if trade_chunks else "",
        "exit_time": trade_chunks[-1]["exit_time"] if trade_chunks else "",
        "exit_price": round(trade_chunks[-1]["exit_price"], 4) if trade_chunks else 0,
        "entry_price": round(entry_price, 4),
        "signal_time": signal_time,
        "entry_score_total": round(signal_score, 4),
    }

def main():
    sb = SupabaseRestClient()
    signal_date = datetime(2026, 5, 28, tzinfo=KST).date()
    entry_date = datetime(2026, 5, 29, tzinfo=KST).date()
    
    print(f"Signal date: {signal_date}, Entry date: {entry_date}")
    print(f"Parameters: SL=-4%, TP=5%, max_holding=3 days, fee=23bps, slip=10bps, min_score=60")
    
    # Prefetch data for both dates
    bars_signal_by_stock = {}
    bars_entry_by_stock = {}
    fetch_start = time.time()
    for sc in KOSPI_TOP_50:
        all_bars = fetch_all_bars_for_stock(sb, sc)
        signal_bars = [b for b in all_bars if b.ts.date() == signal_date]
        entry_bars = [b for b in all_bars if b.ts.date() == entry_date]
        bars_signal_by_stock[sc] = signal_bars
        bars_entry_by_stock[sc] = entry_bars
    print(f"  Prefetch done in {time.time()-fetch_start:.1f}s")
    
    results = []
    exit_reasons = defaultdict(int)
    returns = []
    wins = 0
    for sc in KOSPI_TOP_50:
        signal_bars = bars_signal_by_stock[sc]
        entry_bars = bars_entry_by_stock[sc]
        if not signal_bars or not entry_bars:
            print(f"  {sc}: missing data for signal or entry date")
            continue
        trade = simulate_strategy(signal_bars, entry_bars,
                                  stop_loss_pct=-4.0,
                                  take_profit_pct=5.0,
                                  max_holding_days=3,
                                  fee_bps=23.0,
                                  slippage_bps=10.0,
                                  min_score=60)
        if trade.get('ok'):
            results.append(trade)
            returns.append(trade['net_return_pct'])
            if trade['win']:
                wins += 1
            reason = trade['exit_reason']
            exit_reasons[reason] += 1
            print(f"  {sc}: entry {trade['entry_price']} -> exit {trade['exit_price']} ({reason}) net {trade['net_return_pct']}%")
        else:
            print(f"  {sc}: Blocked: {trade.get('blocking_conditions')}")
    
    print("\n=== Summary ===")
    print(f"Total stocks evaluated: {len(results)}")
    if returns:
        avg_ret = sum(returns)/len(returns)
        win_rate = wins/len(returns)*100
        print(f"Average net return: {avg_ret:.4f}%")
        print(f"Win rate: {win_rate:.2f}%")
        print(f"Min return: {min(returns):.4f}%")
        print(f"Max return: {max(returns):.4f}%")
    print("\nExit reason breakdown:")
    for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reason}: {count} ({count/len(results)*100:.1f}%)")
    
    # Save detailed results
    out_path = Path('/home/june/trading/reports/fujimoto_126_exit_reason_detail.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'signal_date': signal_date.isoformat(),
            'entry_date': entry_date.isoformat(),
            'parameters': {
                'stop_loss_pct': -4.0,
                'take_profit_pct': 5.0,
                'max_holding_days': 3,
                'fee_bps': 23.0,
                'slippage_bps': 10.0,
                'min_score': 60.0,
            },
            'stocks_evaluated': len(results),
            'average_net_return_pct': round(sum(returns)/len(returns), 4) if returns else 0,
            'win_rate_pct': round(wins/len(returns)*100, 2) if results else 0,
            'exit_reason_counts': dict(exit_reasons),
            'detailed_trades': results
        }, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")

if __name__ == '__main__':
    main()