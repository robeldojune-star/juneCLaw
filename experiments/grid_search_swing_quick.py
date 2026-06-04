#!/usr/bin/env python3
"""
Quick grid search for stop loss and take profit parameters for the swing strategy with re-entry.
- Stop loss: negative percent (e.g., -0.3 to -0.8)
- Take profit first target: positive percent (e.g., +1.5 to +3.0)
- Second target: first target + 2.0% (fixed offset)
- Max holding days: 2 to 4
- Uses same re-entry logic as before.
Runs on a small subset of stocks (first 5) and short date range (last 5 days) for speed.
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

def simulate_custom_swing_with_reentry(bars, *, stop_loss_pct, take_profit_pct, take_profit_half_pct, max_holding_days, fee_bps=23.0, slippage_bps=10.0, min_score=60.0):
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
                stop_loss_price = entry_price
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

def run_grid_search(stock_codes, start_date, end_date, sb):
    stop_loss_options = [round(x, 2) for x in [ -0.3, -0.4, -0.5, -0.6, -0.7, -0.8 ]]
    tp_first_options = [round(x, 2) for x in [ 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0 ]]
    max_hold_options = [2, 3, 4]
    best_avg = -float('inf')
    best_params = None
    results = []
    total = len(stop_loss_options) * len(tp_first_options) * len(max_hold_options)
    count = 0
    for sl in stop_loss_options:
        for tp in tp_first_options:
            for mh in max_hold_options:
                count += 1
                tp2 = round(tp + 2.0, 2)
                params = {
                    'stop_loss_pct': sl,
                    'take_profit_pct': tp,
                    'take_profit_half_pct': tp2,
                    'max_holding_days': mh,
                    'fee_bps': 23.0,
                    'slippage_bps': 10.0,
                    'min_score': 60.0
                }
                all_trade_nets = []
                total_days = 0
                for sc in stock_codes:
                    bars = fetch_all_bars_for_stock(sb, sc)
                    bars_by_date = defaultdict(list)
                    for bar in bars:
                        bars_by_date[bar.ts.date()].append(bar)
                    curr = start_date
                    while curr <= end_date:
                        day_bars = bars_by_date.get(curr, [])
                        if not day_bars:
                            curr += timedelta(days=1)
                            continue
                        total_days += 1
                        res = simulate_custom_swing_with_reentry(
                            day_bars,
                            stop_loss_pct=sl,
                            take_profit_pct=tp,
                            take_profit_half_pct=tp2,
                            max_holding_days=mh,
                            fee_bps=23.0,
                            slippage_bps=10.0,
                            min_score=60.0
                        )
                        if res.get('ok'):
                            all_trade_nets.append(res['net_return_pct'])
                        curr += timedelta(days=1)
                if all_trade_nets:
                    avg_ret = sum(all_trade_nets) / len(all_trade_nets)
                    win_rate = sum(1 for r in all_trade_nets if r > 0) / len(all_trade_nets) * 100
                else:
                    avg_ret = 0.0
                    win_rate = 0.0
                results.append({
                    'params': params.copy(),
                    'avg_return': avg_ret,
                    'win_rate': win_rate,
                    'trades': len(all_trade_nets),
                    'days': total_days
                })
                if avg_ret > best_avg:
                    best_avg = avg_ret
                    best_params = params.copy()
                # progress
                if count % 5 == 0 or count == total:
                    print(f"Progress {count}/{total}: SL={sl}, TP1={tp}, TP2={tp2}, MH={mh} -> Avg={avg_ret:.4f}%, WR={win_rate:.2f}%")
    return best_params, best_avg, results

def main():
    sb = SupabaseRestClient()
    # Use very small subset for speed: first 5 stocks
    stock_codes = KOSPI_TOP_50[:5]
    end_date = datetime.now(KST).date()
    start_date = end_date - timedelta(days=4)  # last 5 days
    print(f"Quick grid search on {len(stock_codes)} stocks from {start_date} to {end_date}")
    start_time = time.time()
    best_params, best_avg, all_results = run_grid_search(stock_codes, start_date, end_date, sb)
    elapsed = time.time() - start_time
    print("\n=== Grid Search Complete ===")
    print(f"Best params: {best_params}")
    print(f"Best average net return: {best_avg:.4f}%")
    # Show top 5
    sorted_res = sorted(all_results, key=lambda x: x['avg_return'], reverse=True)[:5]
    print("\nTop 5 parameter sets:")
    for i, r in enumerate(sorted_res, 1):
        p = r['params']
        print(f"{i}. SL={p['stop_loss_pct']}%, TP1={p['take_profit_pct']}%, TP2={p['take_profit_half_pct']}%, MH={p['max_holding_days']} -> Avg={r['avg_return']:.4f}%, WR={r['win_rate']:.2f}%, Trades={r['trades']}/{r['days']}")
    # Save results
    out_path = Path('/home/june/trading/reports/grid_search_swing_quick.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'stocks': stock_codes,
            'date_range': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'best_parameters': best_params,
            'best_avg_return': best_avg,
            'all_results': all_results
        }, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed results saved to {out_path}")
    print(f"Total time: {elapsed:.1f}s")

if __name__ == '__main__':
    main()