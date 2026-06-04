---
name: fujimoto-126-backtest
category: trading
description: Backtest the Fujimoto/Shigeru 1-2-6 trading strategy with custom rules.
---

## Description
Backtest the Fujimoto/Shigeru 1-2-6 trading strategy with custom rules:
- Stop loss: -1% (baseline, but configurable)
- Take profit: +3% (exit 50% of position), remaining 50% moved to break-even then forced exit at +5%
- Maximum holding period: 3 days (swing basis)
- Re-entry after stop-loss allowed if price rebounds above original entry price (configurable)
- Universe: KOSPI top 50 by market cap
- Sentiment filter: previous day foreign+institutional net buying > individual net buying (placeholder)
- Signal generation: existing `evaluate_fujimoto_126` function (score >= 60)

This skill encapsulates the workflow for running the backtest, analyzing results, and visualizing trades.
**Note for this user**: The user prefers Korean language for all communications, so consider providing summaries, notes, and reports in Korean when appropriate.

## When to Use
- You want to evaluate the performance of the Fujimoto 1-2-6 strategy with user-defined risk/reward parameters.
- You need to test variations such as stop-loss re-entry rules, different stop-loss/take-profit levels, or additional intraday filters.
- You want to generate trade-level reports and visual charts (SVG) for manual inspection.
- You want to experiment with alternative signal generation approaches (e.g., RSI-only signals) to compare against the full Fujimoto 1-2-6 filter.
- You need to debug signal generation issues (e.g., understanding why evaluate_fujimoto_126 returns low scores or WATCH/BLOCKED signals).
- You prefer manual verification of trades and visual 1-minute chart validation of entry/exit points, as well as explicit reporting of signal score breakdowns and blocking conditions.
**Note for this user**: The user prefers to verify automated trading systems with manual checks and is prepared to place manual orders if automation does not work as expected. They value visual 1-minute chart validation and explicit reporting of signal score breakdowns and blocking conditions.
## Parameter Tuning Observations

Based on the latest backtesting sessions (grid scans, out-of-sample, and Kospi50 scans):

- **Stop loss and take profit sensitivity**: Wider stop loss (-4% to -5%) combined with wider take profit (+4% to +5%) produced the highest average returns (~+1.82%) with win rates around 76% on the signal date 2026-05-28 across KOSPI Top 50 stocks. The earlier observation that -5% stop loss worsened returns was based on a different exit rule (partial take profit at +3% then break-even then +5%) and limited data; the current take-profit-first strategy behaves differently.
- **Exit reason distribution**: With SL -4%, TP +5%, exits are roughly split between TAKE_PROFIT (~40%), STOP_LOSS (~30%), and TIME_EXIT (~20%), indicating that the profit targets are now being hit frequently enough to drive profitability.
- **Signal frequency**: Using the original min_score=60 yielded signals on about 21/50 stocks for the given date. Lowering min_score to 50 increases signal frequency but may reduce average return per trade; further walk-forward analysis is recommended to find an optimal threshold.
- **Re-entry logic not tested**: None of the tested strategies included re-entry after stop loss. Adding rules such as re-entry if price rebounds above original entry price + X% or if the Fujimoto signal re-triggers could improve expectancy.
- **Sentiment filter pending**: The user’s preferred sentiment filter (previous day foreign+institutional net buying > individual net buying) has not yet been incorporated; applying this filter may increase signal quality at the cost of reduced trade count.
- **Next tuning ideas**:
  - Apply sentiment filter and re-evaluate the SL/TP grid.
  - Conduct walk-forward validation (e.g., 3-day training → 1-day testing) to assess parameter stability.
  - Experiment with re-entry rules after stop loss.
  - Consider alternative exit techniques such as trailing stop profit or volatility-based targets.
  - Increase the backtest window to multiple weeks to ensure results are not overfitted to a single day.

## Prerequisites
- Hermes agent with access to Supabase (intraday_prices and daily_prices tables).
- Kiwoom API token configured in `.env` for intraday data collection (if refreshing data).
- Python environment with required packages (pandas, numpy, etc.) – typically already available in the Hermes workspace.
- The `core.supabase_rest` and `core.fujimoto_126_filter` modules must be importable.

## Steps
1. **Prepare environment**
   - Ensure `.env` contains `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and optionally `KIWOOM_ACCESS_TOKEN`.
   - Verify that the Supabase tables `intraday_prices` (source=`kiwoom_ka10080_minute`, time_frame=`1min`) and `daily_prices` are populated for the desired date range and stocks.
   - Optionally run data collection scripts to refresh intraday data.

2. **Run the backtest script**
   - Execute the appropriate backtest script (e.g., `backtest_fujimoto_custom_swing_with_reentry.py`).
   - Script parameters can be adjusted at the top of the file:
     - `stop_loss_pct` (default -1.0)
     - `take_profit_pct` (default 3.0)
     - `take_profit_half_pct` (default 5.0)
     - `max_holding_days` (default 3)
     - `fee_bps` and `slippage_bps` (default 23 and 10)
     - `min_score` (default 60)
   - The script will output a summary to console and save detailed results to a JSON file under `reports/`.

3. **Review results**
   - Open the generated JSON report (e.g., `reports/fujimoto_126_backtest_custom_swing_with_reentry.json`).
   - Key metrics:
     - Average net return
     - Win rate (percentage of trades with net > 0)
     - Maximum and minimum returns
     - Breakdown by exit reason (TIME_EXIT, STOP_LOSS, TARGET_FULL, MAX_HOLDING_DAYS, END_OF_DATA)
   - Identify stop-loss trades and evaluate potential re-entry improvements.

4. **Visualize trades (optional)**
   - Use plotting scripts such as `plot_trade2_with_signals.py` to generate SVG charts showing price action, entry/exit points, and signal markers.
   - Provide the stock code and date to visualize a specific trade.
   - The script outputs a MEDIA URI that can be viewed in the Hermes WebUI.

5. **Iterate**
   - Adjust parameters (stop-loss, take-profit, re-entry rules) and re-run.
   - Consider adding intraday filters (VWAP, volume spike, bid/ask pressure) by modifying the signal evaluation or the simulation loop.
   - For more robust analysis, extend the backtest period (e.g., 3 months) and increase the stock universe (full KOSPI Top 50).

## Pitfalls & Troubleshooting
- **Missing intraday data**: If a stock/date has no 1-minute bars, treat this as a blocker—do not skip or fallback to daily data, as missing intraday data can produce misleading results. Ensure data collection runs successfully and that the `intraday_prices` table is populated for each stock/date in the backtest period.
- **Stop loss not triggered**: With a tight stop-loss (-1%), many exits may be due to time or end-of-data rather than stop loss. Consider adjusting the stop-loss level if you want to capture more stop-loss events.
- **Stop loss too wide**: Testing stop loss at -5% (instead of -1%) resulted in worse average net return (-1.487% vs -0.716%) due to larger losses per stop-loss event, even though stop-loss frequency increased. This suggests the optimal stop-loss level may be narrower than -5% for this strategy and time period. See `references/stoploss_comparison.md` for detailed comparison.
- **Market practice parameters underperformed**: Testing stop loss parameters in the range of -5% to -8% with take profit targets of 10% to 15% (per common market practice) still resulted in negative average returns in our limited tests. For example, SL=-6%, TP1=12%, TP2=17%, MH=3 yielded -2.0551% average return over 3 days for stock 005930. This suggests that either:
  1. The Fujimoto 1-2-6 signal timing needs adjustment relative to these wider risk/reward parameters
  2. Additional intraday filters (e.g., volume, bid/ask pressure) are needed to improve entry timing
  3. The strategy may require different parameter ranges for this specific market period
- **Re-entry rule too strict**: The default re-entry condition (price > original entry price) may be too conservative. Experiment with alternative rules such as:
  - Price > original entry price + X% (e.g., +0.2%)
  - Price crosses VWAP from below
  - Signal re-triggers (evaluate_fujimoto_126 returns HIGH_CONFIDENCE_CANDIDATE)
- **Performance**: Running over many stocks and days can be slow. Consider limiting the universe or date range for quick experiments.
- **Visualization not displaying**: Ensure the plotting script writes to a temporary file and outputs a MEDIA:data:image/svg+xml;base64,... string. The Hermes WebUI will render inline SVGs correctly.

## Visualization and Reporting Best Practices
- The user prefers visual 1‑minute chart validation of entry/exit points. When generating SVG charts, ensure they are displayed correctly in the Hermes WebUI by using a `MEDIA:/absolute/path/to/file.svg` reference or embedding the SVG as a base64 data URI (`MEDIA:data:image/svg+xml;base64,...`). Direct Markdown image syntax (`![alt](/path)`) does not work for local files in this environment.
- Always report explicit signal score breakdowns and blocking conditions for each trade, as the user values this transparency for manual verification.
- The user prefers separate mock and prod configuration files (e.g., `config/mock.json`, `config/prod.json`) over `_MOCK`/`_PROD` suffixes in `.env` to avoid credential leakage.
- The user prefers Korean language for all communications; consider providing summaries or notes in Korean when appropriate.
## References
## References
- See `references/backtest_notes.md` for session-specific observations and parameter tuning ideas.
- See `references/signal_debug.md` for debugging signal generation issues and component analysis.
- See `references/stoploss_comparison.md` for detailed stop loss comparison.
- See `references/rsi_filter_test.md` for RSI-only signal testing.
- See `references/param_grid_results.md` for full parameter grid search results.
- See `references/scan_kospi50_take_profit.md` for Kospi50 take-profit strategy scan results.
- See `references/session_updates_2026-05-31.md` for session-specific updates from 2026-05-31 including re-entry backtest and master plan.
- See `templates/backtest_config.json` for a starter configuration file.
- See `scripts/analyze_stoploss_reentry.py` for a utility to evaluate stop-loss re-entry opportunities.

## Changelog
- Initial capture of workflow from session on 2026-05-31, including stop-loss re-entry analysis and visualization steps.