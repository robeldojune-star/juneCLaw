# Fujimoto Independent Strategy Validation Workflow

Use this reference when validating the Fujimoto/Shigeru 1-2-6 strategy as an independent strategy in `/home/june/trading`.

## Validation Steps

1. **Data Sufficiency Gate**  
   - Run `scripts/check_backtest_readiness.py` to confirm:  
     - `eligible_stock_days >= 90` (90 trading days of 1‑minute ka10080 data)  
     - `total_variant_trades >= 5` (minimum trade samples)  
   - If gate fails, continue data collection (`scripts/collect_intraday_90d.py`) until satisfied.

2. **Signal Generation**  
   - Use `core/fujimoto_126_filter.evaluate_fujimoto_126(bars)` to generate signals.  
   - Keep `order_execution_enabled = false`, `paper_order_allowed = false`, `real_order_allowed = false`.  
   - Record `score_details` and `blocking_conditions` for each signal.

3. **Trade Simulation**  
   - For each BUY signal, run `simulate_fujimoto_126_trade(bars, entry_idx)` with:  
     - Stop‑loss: –2% of entry price (low‑price trigger)  
     - Take‑profit: +3% of entry price → 50% position close, remaining position trails to break‑even (stop‑loss moved to entry price)  
     - Time‑based exit: 15:20 (market close)  
   - Include fee/slippage assumptions (e.g., 0.015% per side) if desired.

4. **Performance Metrics**  
   - Calculate:  
     - Win rate (% profitable trades)  
     - Profit factor (gross profit / gross loss)  
     - Maximum drawdown  
     - Average net return per trade  
   - Compare against user‑defined thresholds:  
     - Win rate > 52%  
     - Profit factor > 1.3  
     - Max drawdown < 18%

5. **Reporting**  
   - Produce a Korean staged report with:  
     - Completed / pending / blocker summary  
     - Evaluated rows, entries, blocked count, entry rate  
     - Average net return, positive rate, min/max return  
     - Exit reason counts (stop‑loss, take‑profit‑50%, trailing break‑even, time exit)  
     - Blocking condition counts  
     - Links to representative 1‑minute PNG charts (signal/entry/exit markers)  
   - Explicit safety conclusion: paper/real orders remain blocked until validation passes.

6. **Chart Generation**  
   - Reuse `create_backtest_trade_charts.py` (Plotly.js) or create `scripts/create_fujimoto_126_charts.py` to generate HTML/PNG charts showing:  
     - Entry arrow, stop‑loss line, take‑profit level, trailing break‑even point, exit marker.

7. **Git Hygiene**  
   - Commit all changes with clear messages (e.g., "Update Fujimoto independent strategy validation data").  
   - Never commit `.env` or real credentials; use `.env.example` with placeholders.

## Safety Rules

- Do not modify `opening_multi_factor_v1` or production thresholds during validation.  
- Keep all order gates blocked (`paper_order_allowed=false`, `real_order_allowed=false`) until the Leader explicitly approves paper trading.  
- Use only real `intraday_prices` where `source='kiwoom_ka10080_minute'` and `time_frame='1min'`.  
- Never inject synthetic or sampled minute bars to satisfy gate thresholds.

## References

- `core/fujimoto_126_filter.py` – core evaluation and simulation logic  
- `docs/strategies/investment_strategy_registry_v1.md` – strategy registration and status  
- `docs/strategies/fujimoto_independent_plan.md` – detailed execution plan  
- `scripts/check_backtest_readiness.py` – data sufficiency gate  
- `scripts/collect_intraday_90d.py` – intraday data collection  
- `create_backtest_trade_charts.py` – base charting script (Plotly.js)
