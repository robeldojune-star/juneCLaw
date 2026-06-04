# Session Notes: Fujimoto 1-2-6 Backtest Analysis (2026-05-31)

## Key Observations from Session

### 1. Backtest Results Summary
- Total trades: 50 (all stocks/dates where signal triggered)
- Winning trades: 8 (16.0%)
- Average net return: -0.6042%
- Average gross return: 0.0558%
- Average cost: 0.6600% (fee 23bp + slippage 10bp, round-trip)
- Max return: +2.2715% (SK텔레콤 2026-05-29)
- Min return: -1.6600% (multiple stop-loss events)

### 2. Exit Reason Distribution
- TIME_EXIT (15:20 forced intraday close): 36 trades (72%)
- END_OF_DATA: 7 trades (14%)
- STOP_LOSS: 6 trades (12%)
- TARGET_FULL (exit remaining 50% at +5%): 1 trade (2%)

### 3. Stop-Loss Analysis
Out of 6 stop-loss trades:
- Only 2 had intraday data available for re-entry analysis:
  - 028260 (삼성물산) 2026-05-29: entry 416,000 → exit 433,620 (-0.41%)
  - 009150 (삼성전기) 2026-05-27: entry 1,686,000 → exit 1,656,270 (-1.66%)
- Remaining 4 stop-loss trades lacked intraday data (could not analyze re-entry)

### 4. Re-entry Experiment Results (Option A: re-enter if price > original entry)
- 028260 2026-05-29: -0.41% → -0.4322% (slightly worse)
- 009150 2026-05-27: -1.66% → -1.6600% (no change)
- Average change: -0.0111%

### 5. Intraday Post-Stop-Loss Potential (from earlier analysis)
- 028260 2026-05-29: Stop-loss at 411,840, intraday high 433,620 → +5.28% rebound possible
- 009150 2026-05-27: Stop-loss at 1,669,140, intraday high 1,656,270 → -0.77% (no rebound)
- Average maximum potential rebound: +3.05%

## Parameter Tuning Ideas

### Stop-Loss Level
- Current: -1.0%
- Consider testing: -0.5% (more frequent stops, potentially better re-entry opportunities)
- Or: -1.5% (fewer stops, less whipsaw)

### Take-Profit Levels
- Current: +3% (exit 50%), remaining to +5%
- Consider: +4% / +6% or +5% / +7% to capture more trend
- Or use ATR-based dynamic targets

### Re-entry Rules to Test
1. Price > original entry price + X% (X = 0.2, 0.5, 1.0)
2. Price crosses above VWAP (intraday volume-weighted average price)
3. Signal re-trigger: evaluate_fujimoto_126(window) == HIGH_CONFIDENCE_CANDIDATE
4. Combination: price > original entry AND volume > average volume

### Additional Filters
- VWAP condition for entry (price > VWAP)
- Volume spike: current volume > 1.5x average volume
- Bid/ask pressure (if data available): bid_volume / (bid_volume + ask_volume) > 0.5

## Data Issues Noted
1. Intraday data missing bid/ask prices and volumes (all NULL in sampled data)
   - Affects bid/ask pressure filter and realistic slippage simulation
2. foreigner_rate column in daily_prices is NULL for all rows
   - Prevents use of foreign/institutional sentiment filter
3. Some dates lack intraday data entirely (e.g., Samsung 2026-05-20)
   - Need to verify data collection pipeline

## Visualization & Validation
- SVG charts with signal markers (orange triangles) successfully generated
- Best trade visualization: SK텔레콤 2026-05-29 (entry 09:57 97,800 → exit 15:30 100,600, +2.27%)
- Worst trade visualization: LG 2026-05-29 (entry 09:54 99,400 → exit ??? 96,750, -2.66%)
- Charts help validate entry/exit timing against actual price action

## Next Steps
1. Extend backtest to 3-month period with full KOSPI Top 50
2. Test alternative stop-loss levels (-0.5%, -1.5%)
3. Experiment with re-entry rules (VWAP, percentage-based, signal-based)
4. Add intraday filters where data permits (VWAP, volume spike)
5. Fix data collection to capture bid/ask if available from Kiwoom ka10080
6. Implement foreign/institutional data collection for sentiment filter
