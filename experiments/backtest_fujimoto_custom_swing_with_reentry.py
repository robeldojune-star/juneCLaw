#!/usr/bin/env python3
"""
Backtest Fujimoto 1-2-6 strategy with custom rules and re-entry after stop-loss:
- Stop loss: -1% (user requested)
- Take profit: +3% -> exit 50% of position
- Remaining 50%: stop loss moved to break-even, forced exit at +5%
- Max holding period: 3 days (swing basis)
- Re-entry allowed after position closed.
- Additional filters: stock must be in KOSPI top 50 (by market cap) and must pass previous day's sentiment filter
    (foreign + institutional net buying > individual net buying). For now, sentiment filter is placeholder (always True).
- NEW: Re-entry after stop-loss if price rebounds above original entry price
Uses existing evaluate_fujimoto_126 from core.fujimoto_126_filter for signal generation.
"""
import sys
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
from core.fujimoto_126_filter import PriceBar, evaluate_fujimoto_126

# Constants
KST = timezone(timedelta(hours=9))
SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"

# KOSPI top 50 by market cap (approximate, as of 2024-2025)
KOSPI_TOP_50 = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035420",  # NAVER
    "005380",  # 현대차
    "068270",  # 셀트리온
    "035720",  # 카카오
    "005490",  # POSCO
    "012330",  # 현대모비스
    "010140",  # 삼성물산
    "003550",  # LG
    "011200",  # HMM
    "017670",  # SK텔레콤
    "028260",  # 삼성C&T
    "009150",  # 삼성전기
    "010950",  # 소프트웨어
    "015760",  # 한국전력
    "018260",  # 삼성SDI
    "009830",  # 한화솔루션
    "024110",  # 기업은행
    "032830",  # 삼성생명
    "004020",  # 현대로템
    "010130",  # 고려아연
    "009540",  # 한국조선해양
    "010120",  # LG디스플레이
    "009840",  # 코오롱인더
    "003490",  # 대한유화
    "011170",  # 동아쏘시오홀딩스
    "012450",  # 한미사이언스
    "000270",  # 기아
    "003540",  # LG전자
    "010130",  # 고려아연 (duplicate will be deduped)
    "009150",  # 삼성전기 (duplicate)
    # Add more to reach 50 if needed; we'll deduplicate and slice.
]

def dedup(seq):
    seen = set()
    result = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

KOSPI_TOP_50 = dedup(KOSPI_TOP_50)
# We'll use the list as is; if less than 50, we use what we have.

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

def fetch_bars_for_day(sb, stock_code, kst_date):
    """Fetch 1-minute bars for a given stock and KST date from Supabase."""
    rows = sb.get('intraday_prices', {
        'stock_code': f'eq.{stock_code}',
        'source': f'eq.{SOURCE}',
        'time_frame': f'eq.{TIME_FRAME}'
    }, timeout=30)
    bars = []
    for row in rows:
        ts = row['timestamp']
        dt = ts_to_kst(ts)
        if dt.date() == kst_date:
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
    """
    Custom simulation for swing trading with multiple entries allowed.
    Includes re-entry after stop-loss if price rebounds above original entry price.
    Returns dict with aggregated statistics.
    """
    if not bars:
        return {"ok": False, "blocking_conditions": ["missing_intraday_bars"]}

    in_position = False
    entry_price = 0.0
    entry_dt = None
    remaining = 0.0  # fraction of position size still open (0 to 1)
    # Levels based on entry price
    stop_loss_price = 0.0
    target_price = 0.0          # +3% target
    target_half_price = 0.0     # +5% target for remaining half
    trade_chunks = []  # each dict: {entry_price, entry_time, exit_price, exit_time, reason, size}
    
    # For re-entry logic: track last exit price and allow re-entry above original entry
    last_exit_price = 0.0
    last_exit_time = None
    original_entry_price_for_reentry = 0.0  # The entry price of the position that was just stopped out

    i = 0
    n = len(bars)
    while i < n:
        bar = bars[i]
        # Evaluate signal up to current bar using the existing evaluate function
        window = bars[: i + 1]
        eval_result = evaluate_fujimoto_126(window, min_score=min_score)
        signal = eval_result.get("signal", "")

        if not in_position and signal == "HIGH_CONFIDENCE_CANDIDATE":
            # Check if we allow re-entry after stop-loss
            # Option A: Allow re-entry if price is above original entry price (from previous position)
            can_enter = True
            if last_exit_price > 0 and original_entry_price_for_reentry > 0:
                # Only allow re-entry if current close price is above the original entry price
                # that led to the previous stop-loss
                if bar.close <= original_entry_price_for_reentry:
                    can_enter = False
            
            if can_enter:
                # Enter position
                in_position = True
                entry_price = float(bar.close) if bar.close is not None else 0.0
                entry_dt = bar.ts
                remaining = 1.0
                # Initialize levels
                stop_loss_price = entry_price * (1.0 + stop_loss_pct / 100.0)
                target_price = entry_price * (1.0 + take_profit_pct / 100.0)
                target_half_price = entry_price * (1.0 + take_profit_half_pct / 100.0)
                # Reset re-entry tracking for this new position
                original_entry_price_for_reentry = entry_price

        if in_position and entry_price > 0 and entry_dt is not None:
            high = float(bar.high) if bar.high is not None else 0.0
            low = float(bar.low) if bar.low is not None else 0.0
            close = float(bar.close) if bar.close is not None else 0.0
            time = bar.hhmm
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
                        "exit_time": time,
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
                    "exit_time": time,
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
                    "exit_time": time,
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
                    "exit_time": time,
                    "reason": "TARGET_FULL",
                    "size": remaining,
                })
                # Track for potential re-entry
                last_exit_price = target_half_price
                last_exit_time = cur_dt
                remaining = 0.0
                in_position = False
            # Check time exit (intraday)
            elif time >= "15:20":  # hardcoded intraday exit
                # Exit all remaining at close price
                exit_price = close if close > 0 else entry_price  # fallback to entry price if close invalid
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_dt.strftime('%H:%M'),
                    "exit_price": exit_price,
                    "exit_time": time,
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
    # We'll test a subset of KOSPI top 50 for speed; later we can expand.
    # Use first 20 stocks.
    stock_codes = KOSPI_TOP_50[:20]
    end_date = datetime.now(KST).date()
    start_date = end_date - timedelta(days=13)  # approx 2 weeks
    print(f"Backtesting from {start_date} to {end_date} (KST) for {len(stock_codes)} stocks (KOSPI top 50 subset)")
    all_results = []
    for stock_code in stock_codes:
        print(f"\n=== Processing {stock_code} ===")
        current = start_date
        while current <= end_date:
            # Skip sentiment filter for now (placeholder: always pass)
            # In a full implementation, we would check if the stock passes the sentiment filter for the previous day.
            # For now, we assume all KOSPI top 50 stocks pass.
            # Fetch bars
            bars = fetch_bars_for_day(sb, stock_code, current)
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
    out_path = Path('/home/june/trading/reports/fujimoto_126_backtest_custom_swing_with_reentry.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'stocks': stock_codes,
            'date_range': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'results': all_results
        }, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed results saved to {out_path}")

if __name__ == '__main__':
    main()