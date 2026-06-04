#!/usr/bin/env python3
"""
Backtest of Fujimoto 1-2-6 strategy with re-entry after stop loss.
Parameters: SL=-4%, TP=+5%, max holding 3 days, time exit 15:20,
fee 23bps, slippage 10bps, min_score=60.
Re-entry condition: after a stop loss exit, if price recovers above the original entry price
(on the same entry date) we re-enter at that bar's close.
"""
import sys
import json
import csv
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

def simulate_with_reentry(bars_signal, bars_entry,
                          stop_loss_pct=-4.0, take_profit_pct=5.0,
                          max_holding_days=3, fee_bps=23.0, slippage_bps=10.0,
                          min_score=60.0):
    """
    Returns dict with list of trades and summary.
    """
    if not bars_signal or not bars_entry:
        return {"ok": False, "blocking_conditions": ["missing_intraday_bars"], "trades": []}
    
    # 1. Determine signal time (first time STAGE3 appears on signal date)
    signal_time = None
    for bar in bars_signal:
        window = [b for b in bars_signal if b.ts <= bar.ts]
        eval_result = evaluate_fujimoto_126(window, min_score=min_score, include_order_blocks=False)
        if eval_result.get("signal") == "HIGH_CONFIDENCE_CANDIDATE":
            signal_time = bar.hhmm
            break
    if signal_time is None:
        return {"ok": False, "blocking_conditions": ["no_signal_on_signal_date"], "trades": []}
    
    # 2. Find entry bar on entry date with same HH:MM (fallback to first bar)
    entry_bar = None
    for bar in bars_entry:
        if bar.hhmm == signal_time:
            entry_bar = bar
            break
    if entry_bar is None:
        entry_bar = bars_entry[0]
        signal_time = entry_bar.hhmm
    
    # State variables
    in_position = False
    entry_price = 0.0          # price at which we entered current position
    original_entry_price = 0.0 # price of the very first entry (used for re-entry trigger after SL)
    entry_dt = None
    stop_loss_price = 0.0
    target_price = 0.0
    trades = []                # list of dict per trade chunk (we allow only full position entries/exits for simplicity)
    i = 0
    n = len(bars_entry)
    
    # Find start index where hhmm == signal_time
    start_idx = 0
    for idx, bar in enumerate(bars_entry):
        if bar.hhmm == signal_time:
            start_idx = idx
            break
    
    i = start_idx
    while i < n:
        bar = bars_entry[i]
        high = float(bar.high) if bar.high is not None else 0.0
        low = float(bar.low) if bar.low is not None else 0.0
        close = float(bar.close) if bar.close is not None else 0.0
        time_str = bar.hhmm
        cur_dt = bar.ts
        
        if not in_position:
            # Entry condition: either first entry (original_entry_price == 0) or re-entry after SL
            if original_entry_price == 0.0:
                # First entry at signal time
                in_position = True
                entry_price = close
                original_entry_price = entry_price
                entry_dt = cur_dt
                stop_loss_price = entry_price * (1.0 + stop_loss_pct / 100.0)
                target_price = entry_price * (1.0 + take_profit_pct / 100.0)
            else:
                # Check for re-entry: price recovered above original_entry_price
                if close > original_entry_price:
                    in_position = True
                    entry_price = close
                    entry_dt = cur_dt
                    stop_loss_price = entry_price * (1.0 + stop_loss_pct / 100.0)
                    target_price = entry_price * (1.0 + take_profit_pct / 100.0)
                    # Note: we do NOT update original_entry_price here; it remains the price of the first entry
                    # This way re-entry trigger continues to be based on the original entry price.
        else:
            # In position: check exit conditions
            # Max holding period
            days_held = (cur_dt - entry_dt).total_seconds() / (24 * 3600)
            if days_held >= max_holding_days:
                trades.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M') if entry_dt else "",
                    "exit_price": close,
                    "exit_time": time_str,
                    "reason": "MAX_HOLDING_DAYS",
                })
                in_position = False
                # After exit via max holding, we do NOT set original_entry_price (treated as finished)
                original_entry_price = 0.0  # reset so that if price > 0 later we could consider a fresh signal? We'll keep as 0.
                i += 1
                continue
            # Stop loss
            if low <= stop_loss_price:
                trades.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M') if entry_dt else "",
                    "exit_price": stop_loss_price,
                    "exit_time": time_str,
                    "reason": "STOP_LOSS",
                })
                in_position = False
                # Remember the price at which we entered this position for re-entry trigger
                original_entry_price = entry_price  # keep this for re-entry condition
                entry_price = 0.0
                entry_dt = None
                i += 1
                continue
            # Take profit
            elif high >= target_price:
                trades.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M') if entry_dt else "",
                    "exit_price": target_price,
                    "exit_time": time_str,
                    "reason": "TAKE_PROFIT",
                })
                in_position = False
                original_entry_price = 0.0  # reset after TP
                entry_price = 0.0
                entry_dt = None
                i += 1
                continue
            # Time exit (15:20)
            elif time_str >= "15:20":
                exit_price = close if close > 0 else entry_price
                trades.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M') if entry_dt else "",
                    "exit_price": exit_price,
                    "exit_time": time_str,
                    "reason": "TIME_EXIT",
                })
                in_position = False
                original_entry_price = 0.0
                entry_price = 0.0
                entry_dt = None
                i += 1
                continue
        i += 1
    
    # If still in position at end of data, close at last close
    if in_position and entry_price > 0:
        close_price = float(bars_entry[-1].close) if bars_entry[-1].close is not None else entry_price
        trades.append({
            "entry_price": entry_price,
            "entry_time": entry_dt.strftime('%H:%M') if entry_dt else "",
            "exit_price": close_price,
            "exit_time": bars_entry[-1].hhmm,
            "reason": "END_OF_DATA",
        })
    
    if not trades:
        final_eval = evaluate_fujimoto_126(bars_signal, min_score=min_score, include_order_blocks=False)
        return {"ok": False, **final_eval, "trades": []}
    
    # Calculate returns: sum of each trade's P&L weighted by size (all size=1)
    total_return = 0.0
    total_cost = 0.0
    for t in trades:
        entry = t["entry_price"]
        exitp = t["exit_price"]
        if entry > 0:
            gross = (exitp - entry) / entry * 100.0
            cost_per_unit = ((fee_bps + slippage_bps) / 100.0) * 2.0  # round trip
            net = gross - cost_per_unit
            total_return += net
            total_cost += cost_per_unit
    avg_return = total_return / len(trades) if trades else 0.0
    win_count = sum(1 for t in trades if ((float(t["exit_price"])-float(t["entry_price"]))/float(t["entry_price"])*100.0 - ((fee_bps+slippage_bps)/50.0)) > 0)  # approximate
    win_rate = win_count / len(trades) * 100 if trades else 0.0
    
    return {
        "ok": True,
        "trades": trades,
        "avg_return_pct": round(avg_return, 4),
        "win_rate_pct": round(win_rate, 2),
        "total_trades": len(trades),
    }

def main():
    sb = SupabaseRestClient()
    signal_date = datetime(2026, 5, 28, tzinfo=KST).date()
    entry_date = datetime(2026, 5, 29, tzinfo=KST).date()
    
    print(f"Signal date: {signal_date}, Entry date: {entry_date}")
    print(f"Parameters: SL=-4%, TP=+5%, max_holding=3 days, fee=23bps, slip=10bps, min_score=60")
    print(f"Re-entry condition: after SL, re-enter if close > original entry price (same day)")
    
    # Prefetch data
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
    
    all_results = []
    all_returns = []
    total_trades = 0
    wins = 0
    for sc in KOSPI_TOP_50:
        signal_bars = bars_signal_by_stock[sc]
        entry_bars = bars_entry_by_stock[sc]
        if not signal_bars or not entry_bars:
            print(f"  {sc}: missing data for signal or entry date")
            continue
        result = simulate_with_reentry(signal_bars, entry_bars,
                                       stop_loss_pct=-4.0,
                                       take_profit_pct=5.0,
                                       max_holding_days=3,
                                       fee_bps=23.0,
                                       slippage_bps=10.0,
                                       min_score=60)
        if result.get('ok'):
            all_results.append({'stock_code': sc, **result})
            # Compute per trade returns for summary
            for t in result['trades']:
                entry = t["entry_price"]
                exitp = t["exit_price"]
                if entry > 0:
                    gross = (exitp - entry) / entry * 100.0
                    cost = ((23.0+10.0)/100.0)*2.0
                    net = gross - cost
                    all_returns.append(net)
                    if net > 0:
                        wins += 1
            total_trades += result['total_trades']
            print(f"  {sc}: {result['total_trades']} trades, avg {result['avg_return_pct']}%, win {result['win_rate_pct']}%")
        else:
            print(f"  {sc}: Blocked: {result.get('blocking_conditions')}")
    
    print("\n=== Overall Summary ===")
    print(f"Stocks with data: {len(all_results)}")
    print(f"Total trades executed: {total_trades}")
    if all_returns:
        avg_ret = sum(all_returns)/len(all_returns)
        win_rate = wins/len(all_returns)*100
        print(f"Average net return per trade: {avg_ret:.4f}%")
        print(f"Win rate: {win_rate:.2f}%")
        print(f"Min return: {min(all_returns):.4f}%")
        print(f"Max return: {max(all_returns):.4f}%")
    
    # Save results
    out_path = Path('/home/june/trading/reports/fujimoto_126_reentry_backtest.json')
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
                'reentry_condition': 'close > original_entry_price after stop loss (same day)'
            },
            'stocks_evaluated': len(all_results),
            'total_trades': total_trades,
            'average_net_return_pct': round(sum(all_returns)/len(all_returns), 4) if all_returns else 0,
            'win_rate_pct': round(wins/len(all_returns)*100, 2) if all_returns else 0,
            'results': all_results
        }, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")

if __name__ == '__main__':
    main()