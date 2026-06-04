# Stop Loss Comparison: -1% vs -5%

## Backtest Conditions (Common)
- Universe: KOSPI Top 30 (first 30 from Top 50 list)
- Period: 2026-05-19 to 2026-06-01 (10 trading days)
- Strategy: Fujimoto 1-2-6 with re-entry logic
- Take profit: +3% (exit 50%), remaining position forced exit at +5%
- Maximum holding period: 3 days
- Fee/slippage: 23 bps + 10 bps = 33 bps (round-trip 66 bps)
- Signal threshold: evaluate_fujimoto_126 score >= 60

## Results Comparison

| Metric | Stop Loss -1% | Stop Loss -5% | Change |
|--------|---------------|---------------|--------|
| Average Net Return | -0.716% | -1.487% | -0.771 pp |
| Win Rate (Positive Trades) | 21.59% | 24.56% | +2.97 pp |
| Maximum Return | +2.29% | +2.32% | +0.03 pp |
| Maximum Loss | -1.66% | -5.66% | -4.00 pp |
| Total Trading Days | 88 | 57* | -31 days |
| Exit Reason Breakdown | TIME_EXIT 48.9%<br>STOP_LOSS 44.3%<br>END_OF_DATA 5.7%<br>TARGET_FULL 1.1% | (Data not fully aggregated) |  |

\* Note: The -5% backtest counted only days with available intraday data (57 days), while the -1% backtest appeared to count all calendar days in the period (88 days). When comparing like-for-like, the difference in win rate and average return remains significant.

## Key Observations

1. **Worsened Expectancy**: Despite a higher win rate with -5% stop loss, the average net return decreased significantly due to larger losses per stop-loss event.

2. **Stop Loss Frequency**: The absolute number of stop-loss events likely increased with the wider stop loss (contrary to intuition), suggesting that many trades that would have exited via TIME_EXIT or small losses with -1% stop loss instead ran further to hit the -5% stop loss.

3. **Profit Targets Rarely Hit**: In both cases, very few trades reached the profit targets (TARGET_FULL was only 1.1% in the -1% case), indicating that the profit targets may be too conservative relative to intraday volatility or that signals are early.

## Implications for Parameter Tuning

- For this strategy and time period, a stop loss tighter than -5% may be preferable (possibly closer to the original -1%).
- Consider increasing profit targets to better capture intraday swings (e.g., first exit +5% → +10%, second exit +10% → +20%).
- Evaluate reducing maximum holding period to increase chances of intraday exits before time-based exits dominate.
- Consider adding volatility filters to focus on days with sufficient price movement for the strategy to work.

## Files Generated
- -1% results: `reports/fujimoto_126_backtest_custom_swing_with_reentry_optimized.json`
- -5% results: `reports/fujimoto_126_backtest_custom_swing_with_reentry_stoploss_m5.json`
