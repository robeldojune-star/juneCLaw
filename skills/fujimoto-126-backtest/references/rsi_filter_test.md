# RSI Filter Test with Fujimoto 1-2-6 (Session 2026-06-02)

## Objective
Test combining Fujimoto 1-2-6 signal (min_score=50) with RSI(14) ≤ 35 as an entry filter.

## Setup
- Stocks: 005930, 000660 (KOSPI Top 50 sample)
- Dates: 2026-05-27 to 2026-05-29 (3 trading days with data)
- Exit rules: stop loss -5%, first take profit +3% (half), second take profit +5% (full), max holding 3 days, time exit 15:20
- Parameters: min_score=50, rsi_threshold=35, fee_bps=23, slippage_bps=10

## Results
- No trades triggered (0 successful trades over 6 stock-days)
- Fujimoto scores were generally below 50; main blocking conditions:
  - ichimoku_cloud_not_confirmed
  - macd_signal_not_confirmed
  - fujimoto_score_below_min
  - candidate_quality_external_data_not_supplied
- RSI values for the period mostly above 35 (no oversold readings) during the times Fujimoto score was near threshold.

## Analysis
1. **Signal Generation Too Strict**: The Fujimoto 1-2-6 filter requires confirmation from RSI, MACD, and Ichimoku. In the test period, Ichimoku and MACD confirmations were missing, keeping total scores < 50.
2. **RSI Filter Redundancy**: Since the Fujimoto score already includes an RSI component (recovery from ≤30 or trend band 40-75), adding an extra RSI≤35 filter did not add value when the Fujimoto RSI component was not triggered.
3. **Data Limitations**: Missing bid/ask data and foreign/institutional sentiment data affected candidate quality and slippage realism.

## Recommendations
- Lower the Fujimoto min_score threshold (e.g., to 30) to allow entries based on weaker confirmation, then apply RSI≤35 as an additional filter.
- Alternatively, use RSI as a standalone signal (as previously tested) and combine with simple price action rules (e.g., moving average cross) rather than the full Fujimoto filter.
- Improve data collection to capture bid/ask volumes and foreign/institutional flows for better signal realism.

## Files
- Backtest script: `backtest_fujimoto_rsi_combined_v2.py`
- Results: `reports/fujimoto_rsi_combined_backtest.json`