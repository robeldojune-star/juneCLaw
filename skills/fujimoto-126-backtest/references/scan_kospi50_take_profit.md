# Kospi50 Take-Profit Strategy Scan Results

## Test Conditions
- Signal date: 2026-05-28 (Fujimoto 1-2-6 STAGE3 signal detection)
- Entry date: 2026-05-29 (entry at same HH:MM as signal time)
- Universe: KOSPI Top 50 (21 stocks with complete data for both dates)
- Strategy:
  - Detect first STAGE3 signal on signal date
  - Enter next day at same time at close price
  - Exit conditions (in order):
    1. Stop loss: -2%
    2. Take profit: +3%
    3. Maximum holding: 3 days
    4. Time exit: 15:20 KST
  - No re-entry logic
- Parameters: fee_bps=23, slippage_bps=10, min_score=60

## Results Summary
- Total stocks evaluated: 21
- Successful trades: 21/21 (100% signal detection rate)
- Average net return: +0.4328%
- Win rate: 61.90%
- Minimum return: -2.6600%
- Maximum return: +2.3400%

## Exit Reason Breakdown
- TAKE_PROFIT (+3%): 9 trades (42.9%)
- STOP_LOSS (-2%): 7 trades (33.3%)
- TIME_EXIT (15:20): 4 trades (19.0%)
- MAX_HOLDING_DAYS: 0 trades (0.0%)
- END_OF_DATA: 1 trade (4.8%)

## Key Observations
1. **High Signal Detection Rate**: 100% of stocks with data produced a STAGE3 signal on the signal date.
2. **Profit Target Achievement**: 42.9% of trades hit the +3% take profit target.
3. **Stop Loss Frequency**: 33.3% of trades hit the -2% stop loss.
4. **Time Exit Impact**: 19% of trades exited due to time (15:20) without hitting SL or TP.
5. **Comparison to Parameter Grid**: The SL -2%, TP +3% combination from this specific test yielded +0.43% average return, which aligns with the grid search result for that parameter pair (+0.43%).

## Sample Trades (First 5)
- 005930: entry 310500 → exit 317000 (TIME_EXIT) net +1.4334%
- 000660: entry 2352000 → exit 2304960 (STOP_LOSS) net -2.66%
- 402340: entry 1249000 → exit 1224020 (STOP_LOSS) net -2.66%
- 005380: entry 705000 → exit 726150 (TAKE_PROFIT) net +2.34%
- 009150: entry 1999000 → exit 1959020 (STOP_LOSS) net -2.66%

## Recommendations
1. The strategy shows promise with positive expectancy (+0.43%) and reasonable win rate (61.9%).
2. Consider adjusting SL/TP levels based on the parameter grid search (e.g., SL -4%, TP +5% yielded +1.82%).
3. Apply sentiment filter to potentially improve signal quality.
4. Test walk-forward validation to ensure stability across time.
5. Explore re-entry rules after stop loss to capture rebound opportunities.

## Files
Detailed results saved to: `/home/june/trading/reports/fujimoto_126_take_profit_scan_kospi50.json`