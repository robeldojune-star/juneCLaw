#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from core.fujimoto_126_filter import PriceBar, evaluate_fujimoto_126
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))

sb = SupabaseRestClient()
def fetch_bars_kst_date(stock, kst_date):
    start_kst = datetime.combine(kst_date, datetime.min.time())
    end_kst = start_kst + timedelta(days=1)
    start_utc = start_kst - timedelta(hours=9)
    end_utc = end_kst - timedelta(hours=9)
    start_str = start_utc.isoformat()
    end_str = end_utc.isoformat()
    rows = sb.get('intraday_prices', {
        'stock_code': f'eq.{stock}',
        'source': f'eq.kiwoom_ka10080_minute',
        'time_frame': f'eq.1min',
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

# Test one combination
stock = '005930'
end_date = datetime.now(KST).date()
start_date = end_date - timedelta(days=1)  # just one day
dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
bars_by_date = {}
for d in dates:
    bars = fetch_bars_kst_date(sb, stock, d)
    bars_by_date[d] = bars
    print(f"Date {d}: {len(bars)} bars")

# Define a simple simulate function (copy from before)
def simulate_one_day(bars, *, stop_loss_pct, take_profit_pct, take_profit_half_pct, max_holding_days, fee_bps=23.0, slippage_bps=10.0, min_score=60.0):
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

# Run one combination
sl = -0.5
tp = 2.0
mh = 3
tp2 = tp + 2.0
print(f"Testing SL={sl}, TP1={tp}, TP2={tp2}, MH={mh}")
all_trade_nets = []
for d in dates:
    day_bars = bars_by_date[d]
    if not day_bars:
        continue
    res = simulate_one_day(
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
        print(f"  {d}: net={res['net_return_pct']:.4f}%")
    else:
        print(f"  {d}: blocked or no trade: {res}")
if all_trade_nets:
    avg_ret = sum(all_trade_nets) / len(all_trade_nets)
    print(f"Average net return: {avg_ret:.4f}%")
else:
    print("No successful trades")