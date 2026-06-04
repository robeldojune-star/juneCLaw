# Fujimoto 1-2-6 post-backfill + OR comparison workflow

Use this reference when a Fujimoto/Shigeru 1-2-6 signal-mode backtest is blocked or under-sampled because `trading_signals` BUY candidates lack next-trading-day `ka10080` 1-minute bars, and the user wants a decision on whether Fujimoto should be a helper filter or an entry-delay filter.

## Durable workflow

1. **Diagnose next-day minute coverage first**
   - Run/read the missing-next-day diagnostic before changing strategy code.
   - Expected table fields: `covered_count`, `missing_count`, `missing_codes`, `covered_codes`.
   - Treat missing next-day `ka10080` rows as a data coverage problem, not a strategy failure.

2. **Backfill only real ka10080 1-minute bars**
   - Use `scripts/collect_intraday_90d.py` with:
     - `--base-dt` set to the target next trading day, e.g. `20260529`.
     - `--days` narrow enough for the decision sample if the task is urgent, e.g. `3`.
     - `--minute-scope 1`.
     - `--max-requests-per-stock 1` is enough for a next-day + short lookback coverage repair when each response gives ~900 rows.
   - Do not use `ka10005`, synthetic rows, CSV hand edits, or mock OHLCV to fill the gap.
   - Keep collection mode historical/backtest-only; no order side effects.

3. **Re-run coverage immediately after collection**
   - Success criterion for the repaired sample: `missing_count=0` for the target BUY signal date.
   - Save a separate artifact with a post-backfill suffix so before/after coverage remains auditable.

4. **Re-run signals mode backtest**
   - Use the same signal date and limit as the diagnostic.
   - Save separate JSON/MD outputs with a post-backfill suffix.
   - Key metrics to report: evaluation count, entries, blocked, entry rate, avg net %, win rate, min/max, exit reason counts, and blocking condition counts.

5. **Generate visual QA charts by exit bucket**
   - Split results into at least:
     - `TAKE_PROFIT_SIGNAL`
     - `STOP_LOSS_SIGNAL`
     - `TIME_EXIT_SIGNAL`
   - Generate static PNG charts for each bucket. Return `MEDIA:/absolute/path.png` links for representative examples.
   - Visually check that entry/exit markers line up with 1-minute candles and that stop-loss/take-profit cases match the intended thresholds.

6. **Compare OR10/OR30 on the same universe**
   - Use the same stock codes and same next trading day as the Fujimoto signals replay.
   - OR comparison must use true opening ranges:
     - OR10 range complete before entry (`>09:10`).
     - OR30 range complete before entry (`>09:30`).
   - Use the same fee/slippage conventions when possible.
   - If using the existing OR script, note when averages are code-level means rather than trade-level means.

7. **Decision rule**
   - If Fujimoto passes most/all BUY candidates (e.g. all candidates STAGE3), do **not** call it a strong blocking auxiliary filter even if average return is positive.
   - In that case, classify it as:
     - `entry_delay_filter`: delay OR/immediate entry until Fujimoto stage confirmation, or
     - `watchlist_priority`: rank confirmed candidates higher, or
     - `risk_gate`: reduce size/observe when risk flags such as `risk_per_trade_exceeds_limit` occur.
   - Keep `paper_order_allowed=false` and `real_order_allowed=false` until multi-day samples and paper-validation gates pass.

## Reporting template

Include these sections in the user-facing report:

```markdown
## 1. Missing coverage repair
| before missing | after missing | rows collected | alerts/blocking |

## 2. Fujimoto signals replay
| signals | entries | blocked | avg net% | win rate | min | max |

## 3. Exit buckets and charts
- Take-profit examples: MEDIA links
- Stop-loss examples: MEDIA links
- Time-exit examples: MEDIA links

## 4. OR10/OR30 comparison
| strategy | trades/entries | win rate | avg net% | min/risk | exit distribution |

## 5. Decision
- auxiliary blocking filter vs entry-delay filter vs watchlist priority
- order gate status
- next validation steps
```

## Pitfalls

- Do not interpret a positive Fujimoto replay as proof it should become a standalone strategy; check whether it actually filtered anything.
- Do not compare Fujimoto and OR on different dates or different stock universes.
- Do not let partial opening days into OR10/OR30; require complete 09:00~09:30 when using the eligible-day filter.
- Do not modify `opening_multi_factor_v1` during this analysis unless the user explicitly approves a strategy change. Prefer shadow comparison artifacts first.
