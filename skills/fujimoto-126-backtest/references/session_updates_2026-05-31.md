# Session Updates: Fujimoto 1-2-6 Backtest (2026-05-31)

## Summary of work performed in this session

- Ran multiple backtest variations:
  * Base Fujimoto 1-2-6 with stop loss -2%, take profit +3%, time exit 15:20.
  * Parameter grid search over stop loss (-1% to -5%) and take profit (+2% to +5%).
  * Out-of-sample test on April 2026 data using SL=-4%, TP=+5%.
  * KOSPI Top 50 scan for signal date 2026-05-28 → entry 2026-05-29 with SL=-4%, TP=+5%.
  * Added re-entry logic: after a stop‑loss exit, if same‑day close > original entry price, re‑enter.
  * Generated detailed exit‑reason breakdowns (TIME_EXIT, TAKE_PROFIT, STOP_LOSS).
  * Created master plan document outlining next steps toward paper trading and live deployment.

## Key files created or updated

- `backtest_fujimoto_reentry.py` – backtest script with stop‑loss re‑entry rule.
- `exit_reason_breakdown.py` – script to compute exit reason distribution for a given SL/TP.
- `master_plan.md` – high‑level roadmap from strategy validation to paper trading and live trading.
- JSON and Markdown reports under `reports/`:
  * `fujimoto_126_reentry_backtest.json` / `fujimoto_126_reentry_report.md`
  * `fujimoto_126_exit_reason_detail.json` / `fujimoto_126_exit_reason_detail.txt`
  * `fujimoto_126_param_grid.json`
  * `fujimoto_126_take_profit_oos_test.json`
  * `fujimoto_126_take_profit_scan_kospi50.json`
- Updated references:
  * `references/backtest_notes.md` – prior session notes (now expanded).
  * `references/param_grid_results.md` – results from grid search.
  * `references/scan_kospi50_take_profit.md` – Kospi50 take‑profit scan.
  * `references/signal_debug.md` – signal component analysis.

## Main takeaways for future work

1. **Re‑entry improves trade frequency but reduces per‑trade expectancy**:  
   - Without re‑entry: avg +1.8176 %, win 76.2 % (21 trades).  
   - With re‑entry: avg +1.5056 %, win 67.6 % (37 trades).  
   - Total period return increased because of higher trade count.

2. **Stop‑loss ‑4 % / take‑profit +5 % remains a strong baseline** (from grid scan).  
   - Wider SL/TP combos (‑4%/‒5% with TP +4%/+5%) gave highest average returns in prior scans.

3. **Sentiment filter and walk‑forward validation are pending** – identified as next priority items in master plan.

4. **Visualization and reporting best practices** confirmed:  
   - Use `MEDIA:/absolute/path.svg` or base64 data URI for inline SVG in Hermes WebUI.  
   - Always include signal score breakdown and blocking conditions for manual verification.

## Suggested next steps (from master plan)

1. Integrate sentiment filter (foreign + institutional net buying > individual net buying).  
2. Perform walk‑forward validation (e.g., 10‑day train → 1‑day test) to test parameter stability.  
3. Build paper‑trading environment with daily signal generation and mock order logging.  
4. Add position sizing based on volatility or fixed fractional risk.  
5. Prepare for live trading with Kiwoom order API, risk checks, and alerting.

---
*This file is intended to be referenced from the main SKILL.md of the fujimoto-126-backtest skill.*