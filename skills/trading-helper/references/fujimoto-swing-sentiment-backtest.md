# Fujimoto Swing & Sentiment Backtest Reference

## Overview
This document captures the backtest workflow for evaluating the Fujimoto/Shigeru 1-2-6 strategy as a swing trade with sentiment filtering, executed in the session on 2026-05-31.

## Key Modifications
- **Stop Loss**: -1% (user requested, tighter than original -2%)
- **Take Profit**: +3% → exit 50% of position; remaining 50% has break-even stop loss and forced exit at +5%
- **Max Holding Period**: 3 days (swing basis)
- **Re-entry**: Allowed after position fully closed
- **Universe**: KOSPI top 50 by market cap (approximate list)
- **Sentiment Filter**: Previous day foreign + institutional net buying > individual net buying (placeholder: always passed in this run; to be implemented via Kiwoom API ka10008/ka10009)
- **Signal Generation**: Uses existing `evaluate_fujimoto_126` from `core.fujimoto_126_filter` with `min_score=60.0`
- **Execution Simulator**: Custom simulation script (`backtest_fujimoto_custom_swing.py`) that processes daily 1-minute bars from Supabase (source=`kiwoom_ka10080_minute`, time_frame=`1min`) and applies the above rules.

## Results Summary (20 stocks, ~2 weeks)
- Total evaluated days (stock × day): 47
- Successful trades (signal generated): 47/47 (100%)
- Average net return: -0.5849%
- Positive rate: 14.89% (7/47 trades profitable)
- Max return: +2.2715% (018260, TARGET_FULL)
- Max loss: -1.6600% (stop loss -1% + fees/slippage)

## Observations
- Many exits were due to TIME_EXIT (15:20 intraday close), indicating signals often did not reach profit targets within the day.
- Some trades hit STOP_LOSS (-1%) or reached TARGET_FULL (+5%).
- The low positive rate suggests the signal may need refinement (e.g., higher min_score, different universe) or the profit targets are too aggressive for the typical intraday move after signal.
- The sentiment filter was not active; implementing it may reduce trade frequency but increase quality.

## Files Involved
- `core/fujimoto_126_filter.py` (unchanged, provides `evaluate_fujimoto_126` and `PriceBar`)
- `backtest_fujimoto_custom_swing.py` (main backtest script)
- `/home/june/trading/reports/fujimoto_126_backtest_custom_swing.json` (detailed results)
- `references/fujimoto-swing-sentiment-backtest.md` (this document)

## Next Steps
1. Implement real sentiment filter using Kiwoom API (`ka10008` for foreign, `ka10009` for institutional) and compare net buying vs individual.
2. Tune parameters: test stop loss -0.5%, take profit +2.5%/+4.5%, or adjust min_score to 65.
3. Extend backtest period to 3 months to assess stability.
4. Generate signal‑entry‑exit charts for representative winning/losing trades using `scripts/create_fujimoto_126_charts.py` (adapted for swing).