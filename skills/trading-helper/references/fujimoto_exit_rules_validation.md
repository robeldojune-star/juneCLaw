# Fujimoto Shigeru 1-2-6 Exit Rules Validation Summary

This document captures key validation points and lessons learned during the implementation and backtesting of the Fujimoto Shigeru 1-2-6 strategy with specific exit rules.

## 1. Entry Timing Verification
- Ensure entries occur **only after** the signal is confirmed (i.e., on the bar where `evaluate_fujimoto_126` returns `HIGH_CONFIDENCE_CANDIDATE`).
- In a bar-by-bar simulation, the evaluation window must be `bars[: current_index + 1]`; entry must not be triggered on prior bars.
- Verified via signal timestamps: first entry signals appeared at specific times (e.g., 10:29 for 005380, 10:08 for 005930) and entries were simulated at the close of those bars.

## 2. Indicator Calculation Window Validation
- Ichimoku `Span B` requires 52 periods of historical data. Confirm that the strategy does not use `Span B` values before 52 bars are available.
- General rule: any indicator requiring N periods should not be used for signal generation until at least N bars have been processed.
- Verified by checking that at the first signal bar, the Ichimoku components (`span_a`, `span_b`, `tenkan`, `kijun`) were all non-null.

## 3. Avoiding Premature Entries on Doji/Long Upper Wick Breakouts
- The strategy should **not** automatically buy on doji (body < 10% of prior day's range) or long upper wick (upper shadow > 2× body) breakouts unless the full 1-2-6 signal is present.
- Validation on sample signals:
  - 005930: doji present (body 0) but upper wick condition not met (upper shadow 500, body 0 → condition fails because body is zero).
  - 000660: upper wick present (upper shadow 4000, body 1000 → upper shadow > 2× body) but not a doji.
- Conclusion: no signal satisfied both doji **and** long upper wick simultaneously; thus the strategy did not erroneously enter on these patterns alone.

## 4. Exit Rules Implementation (as requested)
The implemented exit rules in `simulate_fujimoto_126_trade` are:
- **Stop Loss**: –2% from entry price (exit remaining position if low ≤ stop price).
- **Take Profit**: +3% from entry price → exit 50% of position at that price.
- **Remaining 50%**: stop loss moved to break-even (entry price); forced exit at +5% from entry price.
- **Time Exit**: close all remaining positions at 15:20 (HH:MM).
- **Re-entry**: allowed after a position is fully closed; new entries permitted on the same day if a new signal forms.

## 5. Backtesting Results (2026-05-18 to 2026-05-31, KST)
- **Stocks**: 005930, 000660, 005380, 035420, 068270 (5 stocks).
- **Evaluation Days**: 12 (approx. 2.4 days per stock, based on available intraday data).
- **Trades Simulated**: 12/12 days produced a signal and were simulated.
- **Average Net Return**: –0.9566%.
- **Positive Rate**: 25.0% (3 profitable trades out of 12).
- **Max Return**: +0.3084%.
- **Max Loss**: –2.6600% (stop loss –2% plus fees/slippage).
- **Primary Exit Reasons**: Many trades exited via time exit (15:20) due to insufficient price movement to reach profit targets; some hit stop loss.

## 6. Lessons and Next Steps
- The current parameter set (stop –2%, target +3%/+5%) yields negative expectancy under the observed market conditions.
- Consider adjusting profit targets or stop loss to improve win rate and profit factor, or tightening entry criteria (higher `min_score`) to trade only on stronger signals.
- Validate any parameter changes with out-of-sample data or extended history.
- Use chart visualizations (e.g., via `scripts/create_fujimoto_126_charts.py`) to inspect entry/exit timing for individual trades.

## Files Referenced
- Core strategy logic: `core/fujimoto_126_filter.py`
- Backtesting script: `scripts/backtest_fujimoto_kst_v2.py`
- Signal verification: `verify_fujimoto_signals.py`