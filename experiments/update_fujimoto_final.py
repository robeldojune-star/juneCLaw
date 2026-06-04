import sys
import os

sys.path.insert(0, '/home/june/trading')

backup_path = '/home/june/trading/core/fujimoto_126_filter.py.backup'
target_path = '/home/june/trading/core/fujimoto_126_filter.py'

with open(backup_path, 'r') as f:
    lines = f.readlines()

# Find the start and end of the simulate_fujimoto_126_trade function
start_idx = -1
for i, line in enumerate(lines):
    if line.strip().startswith('def simulate_fujimoto_126_trade('):
        start_idx = i
        break

if start_idx == -1:
    print("Error: Could not find simulate_fujimoto_126_trade function in backup")
    sys.exit(1)

# Find the end of the function: look for the next line that starts with 'def ' or 'class ' after start_idx
end_idx = len(lines)
for i in range(start_idx + 1, len(lines)):
    stripped = lines[i].strip()
    if stripped.startswith('def ') or stripped.startswith('class '):
        end_idx = i
        break

# New function content
new_func = '''def simulate_fujimoto_126_trade(
    bars: list[PriceBar],
    *,
    min_score: float = 60.0,
    stop_loss_pct: float = -2.0,
    take_profit_pct: float = 3.0,
    take_profit_half_pct: float = 5.0,  # additional forced exit at +5% for remaining half
    time_exit: str = "15:20",
    fee_bps: float = 23.0,
    slippage_bps: float = 10.0,
) -> dict[str, Any]:
    """Simulate read-only intraday trades with multiple entries allowed.
    Rules:
    - Entry: when evaluate_fujimoto_126 returns signal == HIGH_CONFIDENCE_CANDIDATE.
    - Position size: 1 unit per entry (we treat each entry as size 1.0 for simplicity).
    - Stop loss: -2% from entry price.
    - Take profit: +3% from entry price -> exit 50% of position at that price.
    - Remaining 50%: stop loss moved to break-even (entry price) and forced exit at +5% from entry.
    - Time exit: close all remaining at time_exit (HH:MM).
    - Re-entry allowed after a position is fully closed.
    Returns aggregated trade statistics.
    """
    if not bars:
        return {"ok": False, "blocking_conditions": ["missing_intraday_bars", *ORDER_BLOCKS], "paper_order_allowed": False, "real_order_allowed": False, "order_execution_enabled": False}

    # State
    in_position = False
    entry_price = 0.0
    entry_time = ""
    remaining = 0.0  # fraction of position size still open (0 to 1)
    # Levels based on entry price
    stop_loss_price = 0.0
    target_price = 0.0          # +3% target
    target_half_price = 0.0     # +5% target for remaining half
    # Trade logs
    trade_chunks = []  # each dict: {entry_price, entry_time, exit_price, exit_time, reason, size}

    i = 0
    n = len(bars)
    while i < n:
        bar = bars[i]
        # Evaluate signal up to current bar
        window = bars[: i + 1]
        eval_result = evaluate_fujimoto_126(window, min_score=min_score)
        signal = eval_result.get("signal", "")

        if not in_position and signal == "HIGH_CONFIDENCE_CANDIDATE":
            # Enter position
            in_position = True
            entry_price = float(bar.close) if bar.close is not None else 0.0
            entry_time = bar.hhmm
            remaining = 1.0
            # Initialize levels
            stop_loss_price = entry_price * (1.0 + stop_loss_pct / 100.0)
            target_price = entry_price * (1.0 + take_profit_pct / 100.0)
            target_half_price = entry_price * (1.0 + take_profit_half_pct / 100.0)

        if in_position and entry_price > 0:
            high = float(bar.high) if bar.high is not None else 0.0
            low = float(bar.low) if bar.low is not None else 0.0
            close = float(bar.close) if bar.close is not None else 0.0
            time = bar.hhmm

            # Check stop loss
            if remaining > 0 and low <= stop_loss_price:
                # Exit all remaining at stop loss price
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_time,
                    "exit_price": stop_loss_price,
                    "exit_time": time,
                    "reason": "STOP_LOSS",
                    "size": remaining,
                })
                remaining = 0.0
                in_position = False
                # After exit, we will look for next signal in next iteration
                # (do not skip this bar; we will increment i and continue)
            # Check take profit (first half) only if we still have full position
            elif remaining == 1.0 and high >= target_price:
                # Exit 50% at target price
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_time,
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
                    "entry_time": entry_time,
                    "exit_price": target_half_price,
                    "exit_time": time,
                    "reason": "TARGET_FULL",
                    "size": remaining,
                })
                remaining = 0.0
                in_position = False
            # Check time exit
            elif time >= time_exit:
                # Exit all remaining at close price
                exit_price = close if close > 0 else entry_price  # fallback to entry price if close invalid
                trade_chunks.append({
                    "entry_price": entry_price,
                    "entry_time": entry_time,
                    "exit_price": exit_price,
                    "exit_time": time,
                    "reason": "TIME_EXIT",
                    "size": remaining,
                })
                remaining = 0.0
                in_position = False
            # If price moves but no exit condition, we continue holding

        i += 1

    # After loop, if still in position, close at last close
    if in_position and remaining > 0 and entry_price > 0:
        close_price = float(bars[-1].close) if bars[-1].close is not None else entry_price
        trade_chunks.append({
            "entry_price": entry_price,
            "entry_time": entry_time,
            "exit_price": close_price,
            "exit_time": bars[-1].hhmm,
            "reason": "END_OF_DATA",
            "size": remaining,
        })
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

    # Determine overall signal: if any trade was profitable? We'll just set based on last trade? 
    # For simplicity, we keep signal as HIGH_CONFIDENCE_CANDIDATE if we had any trades.
    signal = "HIGH_CONFIDENCE_CANDIDATE" if trade_chunks else "BLOCKED"

    return {
        "ok": True,
        "strategy": STRATEGY_ID,
        # For compatibility with existing expectations, we keep these fields from the last trade?
        # We'll set to the first trade's entry details for simplicity.
        "entry_time": trade_chunks[0]["entry_time"] if trade_chunks else "",
        "entry_price": _round(trade_chunks[0]["entry_price"]) if trade_chunks else 0,
        "entry_stage": "UNKNOWN",  # we could compute but skip
        "position_units": 0,  # not applicable
        "entry_score_total": 0.0,  # we could average but skip
        "entry_score_details": {},
        "exit_time": trade_chunks[-1]["exit_time"] if trade_chunks else "",
        "exit_price": _round(trade_chunks[-1]["exit_price"]) if trade_chunks else 0,
        "exit_reason": trade_chunks[-1]["reason"] if trade_chunks else "",
        "gross_return_pct": _round(avg_gross),
        "cost_pct": _round(avg_cost),
        "net_return_pct": _round(net),
        "blocking_conditions": [],  # no blocking conditions if we have trades
        "paper_order_allowed": False,
        "real_order_allowed": False,
        "order_execution_enabled": False,
    }
'''

# Build new file: lines before start_idx + new_func + lines from end_idx onwards
new_lines = lines[:start_idx] + [new_func] + lines[end_idx:]

# Write backup of current target just in case
if os.path.exists(target_path):
    os.rename(target_path, target_path + '.bak2')

with open(target_path, 'w') as f:
    f.writelines(new_lines)

print("Successfully updated simulate_fujimoto_126_trade function in", target_path)