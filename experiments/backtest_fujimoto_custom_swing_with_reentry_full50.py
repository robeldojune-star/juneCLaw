#!/usr/bin/env python3
"""
Optimized backtest of Fujimoto 1-2-6 strategy with custom rules and re-entry,
using actual KOSPI Top 50 list from kospi_top50_common_stocks_marketcap_naver.csv.
Optimizations:
- Fetch intraday bars once per stock for the entire date range (instead of per day)
- Group bars by date in Python
- Progress logging
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

# Constants
KST = timezone(timedelta(hours=9))
SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"

def load_kospi_top50(csv_path='/home/june/trading/data/kospi_top50_common_stocks_marketcap_naver.csv'):
    """Load KOSPI Top 50 stock codes from the CSV."""
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
        # fallback to hardcoded list (but we want to avoid)
        codes = [
            "005930", "000660", "035420", "005380", "068270", "035720", "005490",
            "012330", "010140", "003550", "011200", "017670", "028260", "009150",
            "010950", "015760", "018260", "009830", "024110", "032830", "004020",
            "010130", "009540", "010120", "009840", "003490", "011170", "012450",
            "000270", "003540", "010130", "009150",  # duplicates will be deduped later
        ]
    # deduplicate preserving order
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
    """Convert timestamp to KST datetime."""
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
    """Fetch all 1-minute bars for a given stock from Supabase."""
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

def simulate_custom_swing_with_reentry(bars, *, stop_loss_pct=-1.0, take_profit_pct=3.0, take_profit_half_pct=5.0, max_holding_days=3, fee_bps=23.0, slippage_bps=10.0, min_score=60.0):
    """Custom simulation for swing trading with multiple entries allowed."""
    if not bars:
        return {"ok": False, "blocking_conditions": ["missing_intraday_bars"]}

    in_position = False
    entry_price = 0.0
    entry_dt = None
    remaining = 0.0
    stop_loss_price = 0.0
    target_price = 0.0
    target_half_price = 0.0
    trade_chunks = []
    last_exit_price = 0.0
    last_exit_time = None
    original_entry_price_for_reentry = 0.0

    i = 0
    n = len(bars)
    while i < n:
        bar = bars[i]
        window = bars[: i + 1]
        eval_result = evaluate_fujimoto_126(window, min_score=min_score)
        signal = eval_result.get("signal", "")

        if not in_position and signal == "HIGH_CONFIDENCE_CANDIDATE":
            can_enter = True
            if last_exit_price > 0 and original_entry_price_for_reentry > 0:
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
                original_entry_price_for_reentry = entry_price

        if in_position and entry_price > 0 and entry_dt is not None:
            high = float(bar.high) if bar.high is not None else 0.0
            low = float(bar.low) if bar.low is not None else 0.0
            close = float(bar.close) if bar.close is not None else 0.0
            time_str = bar.hhmm
            cur_dt = bar.ts

            # Check max holding days
            if remaining > 0:
                days_held = (cur_dt - entry_dt).total_seconds() / (24 * 3600)
                if days_held >= max_holding_days:
                    # Exit all remaining at close price
                    trade_chunks.append({
                        "entry_price": entry_price,
                        "entry_time": entry_dt.strftime('%H:%M'),
                        "exit_price": close,
                        "exit_time": time_str,
                        "reason": "MAX_HOLDING_DAYS",
                        "size": remaining,
                    })
                    # Track for potential re-entry
                    last_exit_price = close
                    last_exit_time = cur_dt
                    remaining = 0.0
                    in_position = False
                    i += 1
                    continue

            # Check stop loss
            if remaining > 0 and low <= stop_loss_price:
                # Exit all remaining at stop loss price
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": stop_loss_price,
                    "exit_time": time_str,
                    "reason": "STOP_LOSS",
                    "size": remaining,
                })
                # Track for potential re-entry: remember the original entry price
                last_exit_price = stop_loss_price
                last_exit_time = cur_dt
                original_entry_price_for_reentry = entry_price  # This is what we compare against for re-entry
                remaining = 0.0
                in_position = False
                i += 1
                continue
            # Check take profit (first half) only if we still have full position
            elif remaining == 1.0 and high >= target_price:
                # Exit 50% at target price
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": target_price,
                    "exit_time": time_str,
                    "reason": "TARGET_HALF",
                    "size": 0.5,
                })
                remaining = 0.5
                # Adjust stop loss to break-even and set target to forced exit at +5%
                stop_loss_price = entry_price  # break-even
                target_price = target_half_price  # now target is the forced exit at +5%
            # Check forced exit at +5% for remaining half
            elif remaining == 0.5 and high >= target_half_price:
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": target_half_price,
                    "exit_time": time_str,
                    "reason": "TARGET_FULL",
                    "size": remaining,
                })
                # Track for potential re-entry
                last_exit_price = target_half_price
                last_exit_time = cur_dt
                remaining = 0.0
                in_position = False
            # Check time exit (intraday)
            elif time_str >= "15:20":  # hardcoded intraday exit
                # Exit all remaining at close price
                exit_price = close if close > 0 else entry_price  # fallback to entry price if close invalid
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": exit_price,
                    "exit_time": time_str,
                    "reason": "TIME_EXIT",
                    "size": remaining,
                })
                # Track for potential re-entry
                last_exit_price = exit_price
                last_exit_time = cur_dt
                remaining = 0.0
                in_position = False
            # If price moves but no exit condition, we continue holding

        i += 1

    # After loop, if still in position, close at last close
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
        # Track for potential re-entry
        last_exit_price = close_price
        last_exit_time = bars[-1].ts
        remaining = 0.0
        in_position = False

    # If no trades occurred, return blocked with eval of full series
    if not trade_chunks:
        final_eval = evaluate_fujimoto_126(bars, min_score=min_score)
        return {"ok": False, **final_eval}

    # Compute aggregated statistics
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
            # Cost per unit: round-trip fee + slippage
            cost_per_unit = ((fee_bps + slippage_bps) / 100.0) * 2.0
            total_cost += cost_per_unit * size
        else:
            # invalid entry price, treat as zero gross
            pass

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
        "strategy": "fujimoto_126_trend_confirmation_v1",
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
    # Use FULL KOSPI TOP 50 list
    stock_codes = KOSPI_TOP_50
    end_date = datetime.now(KST).date()
    start_date = end_date - timedelta(days=13)  # approx 2 weeks
    print(f"Backtesting from {start_date} to {end_date} (KST) for {len(stock_codes)} stocks (FULL KOSPI top 50)")
    
    all_results = []
    start_time = time.time()
    
    for idx, stock_code in enumerate(stock_codes, 1):
        print(f"\n[{idx}/{len(stock_codes)}] Processing {stock_code}...")
        stock_start_time = time.time()
        
        # Fetch all bars for this stock once
        all_bars = fetch_all_bars_for_stock(sb, stock_code)
        
        # Group bars by date
        bars_by_date = defaultdict(list)
        for bar in all_bars:
            bars_by_date[bar.ts.date()].append(bar)
        
        current = start_date
        while current <= end_date:
            bars = bars_by_date.get(current, [])
            if not bars:
                current += timedelta(days=1)
                continue
            print(f"  {current}: {len(bars)} bars")
            # Run simulation with stop loss -1% and max holding 3 days
            trade = simulate_custom_swing_with_reentry(
                bars,
                stop_loss_pct=-1.0,
                take_profit_pct=3.0,
                take_profit_half_pct=5.0,
                max_holding_days=3,
                fee_bps=23.0,
                slippage_bps=10.0,
                min_score=60.0
            )
            trade['stock_code'] = stock_code
            trade['date'] = current.isoformat()
            all_results.append(trade)
            if trade.get('ok'):
                print(f"    -> OK: entry={trade.get('entry_price')}, exit={trade.get('exit_price')}, reason={trade.get('exit_reason')}, net={trade.get('net_return_pct')}%")
            else:
                print(f"    -> Blocked: {trade.get('blocking_conditions')}")
            current += timedelta(days=1)
        
        stock_elapsed = time.time() - stock_start_time
        print(f"  Completed {stock_code} in {stock_elapsed:.1f}s")
    
    # Summary
    print("\n=== Summary ===")
    successful = [r for r in all_results if r.get('ok')]
    if successful:
        returns = [r['net_return_pct'] for r in successful if r.get('net_return_pct') is not None]
        if returns:
            avg_return = sum(returns) / len(returns)
            positive_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
            print(f"Total days evaluated: {len(all_results)}")
            print(f"Successful trades: {len(successful)}/{len(all_results)}")
            print(f"Average net return: {avg_return:.4f}%")
            print(f"Positive rate: {positive_rate:.2f}%")
            print(f"Min return: {min(returns):.4f}%")
            print(f"Max return: {max(returns):.4f}%")
        else:
            print("No returns available.")
    else:
        print("No successful trades.")
    
    # Save results
    out_path = Path('/home/june/trading/reports/fujimoto_126_backtest_custom_swing_with_reentry_full50.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'stocks': stock_codes,
            'date_range': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'results': all_results
        }, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed results saved to {out_path}")
    
    elapsed = time.time() - start_time
    print(f"\nTotal execution time: {elapsed:.1f}s")

if __name__ == '__main__':
    main()