# Entry Variant Comparison Backtest

Use this reference when the user asks to compare OR breakout entry mechanics without changing the live/paper trading strategy.

## Trigger phrases
- "OR 돌파 직후 즉시 진입 vs pullback/rebreak 진입 비교"
- "09:10~10:00 진입 제한 추가"
- "돌파봉 거래량 조건 추가"
- "진입 후 3~5분 내 급락 필터"
- "OR10/OR30 대신 10:00 확인 진입 비교"

## Safety boundary
- Treat this as **read-only research** unless the user explicitly approves strategy/order changes.
- Do not modify `orders`, `positions`, paper execution, or real order paths.
- It is acceptable to write report artifacts and test files.
- Keep production thresholds/weights/order behavior untouched during comparison.

## Recommended variants
Evaluate both OR10 and OR30 where possible:

1. `immediate_breakout`: first post-OR bar whose high breaks the opening range high; enter at bar close.
2. `pullback_rebreak`: after first breakout, require pullback to opening high or below, then enter on a rebreak above opening high.
3. `entry_window`: immediate breakout but only before a configured cutoff, typically `10:00`.
4. `volume_confirmed_breakout`: immediate breakout plus breakout-bar volume >= opening-range average volume × multiplier, initially `1.5`.
5. `early_drop_filtered_breakout`: immediate breakout candidate is rejected if the next 3~5 bars suffer a fast adverse move, e.g. low <= entry × `(1 - 0.7%)`.
6. `ten_oclock_confirmation`: enter at/after `10:00` only if the 10:00 close is above the opening range high.

## Data source discipline
- Daily BUY candidates come from real `trading_signals` rows.
- Minute replay uses real `intraday_prices` rows where `source='kiwoom_ka10080_minute'` and `time_frame='1min'`.
- For a daily `signal_date`, locate the next tradable minute day from `intraday_prices`, not only from `daily_prices`:
  ```sql
  select min((timestamp at time zone 'Asia/Seoul')::date)
  from intraday_prices
  where stock_code = :stock_code
    and source = 'kiwoom_ka10080_minute'
    and time_frame = '1min'
    and (timestamp at time zone 'Asia/Seoul')::date > :signal_day;
  ```
- If next-day minute bars are missing, record a blocking condition such as `next_trading_day_missing`; do not replay the same day.

## TDD/verification pattern
1. Write small deterministic unit tests for entry semantics before implementation.
2. Use synthetic `Bar` rows only inside unit tests, not in performance results.
3. Verify RED failure from a missing module/function, then implement minimal logic.
4. Run the focused test suite, e.g. `uv run --with pytest pytest tests/test_entry_variant_comparison.py -q`.
5. Run the real-data report with psycopg isolated through uv if the host Python lacks it:
   ```bash
   uv run --with 'psycopg[binary]' python scripts/backtest_entry_variant_comparison.py \
     --start-date YYYY-MM-DD \
     --end-date YYYY-MM-DD \
     --limit-per-date 100 \
     --json-out reports/entry_variant_comparison_latest.json \
     --md-out reports/entry_variant_comparison_latest.md
   ```

## Report shape
Include:
- target `signal_dates`
- BUY signal count
- count of missing next-day minute bars
- evaluated result count
- per-variant `signals_seen`, `entries`, `entry_rate_pct`, `avg_net`, `positive_rate_pct`, exit reason counts, and blocking condition counts
- clear warning when only one signal date or only a few evaluated stocks exist

## Interpretation rules
- A filter with zero entries is not proof of profitability; describe it as loss avoidance / opportunity reduction until more samples exist.
- If every entered trade stops out, do not recommend unblocking paper/real orders.
- If `entry_window` equals `immediate_breakout`, explain that current entries already happened inside the window.
- If `early_drop_filtered_breakout` blocks all losing OR10 entries in a tiny sample, keep it as a candidate filter but require sample expansion before adoption.
- If `ten_oclock_confirmation` creates zero entries, treat it as a conservative guardrail, not a deployable strategy.
- Always separate strategy research findings from live order enablement gates.

## Common pitfalls
- Do not classify missing host `python`, `pytest`, or `psycopg` as durable project failures; use the project’s runtime (`uv run --with ...`) and move on.
- Do not let test fixtures leak into real market-data reports.
- Do not update production `opening_strategy` behavior while the request is only a comparison/research ask.
- Preserve the user’s expectation for Korean staged reports with completed/pending/blocker summaries when presenting results.
