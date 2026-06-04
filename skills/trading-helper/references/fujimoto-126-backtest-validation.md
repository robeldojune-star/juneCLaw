# Fujimoto 1-2-6 Backtest Validation Workflow

Use this reference when turning a Fujimoto/Shigeru 1-2-6 strategy report into code and real-data validation for `/home/june/trading`.

## Scope and safety boundary

- Treat the work as **read-only research/backtest** unless the user explicitly approves strategy/order changes.
- Do not modify `orders`, `positions`, paper execution, real order paths, production thresholds, or `opening_multi_factor_v1` behavior during validation.
- Always keep returned results explicit:
  - `paper_order_allowed=false`
  - `real_order_allowed=false`
  - `order_execution_enabled=false`
  - `paper_order_blocked`, `real_order_blocked` in `blocking_conditions`
- Use only real `intraday_prices` rows where:
  - `source='kiwoom_ka10080_minute'`
  - `time_frame='1min'`

## Recommended implementation shape

1. Create a pure calculation module, e.g. `core/fujimoto_126_filter.py`:
   - `PriceBar` dataclass with `ts`, `hhmm`, `open`, `high`, `low`, `close`, `volume`.
   - RSI series calculation.
   - MACD line/signal/histogram calculation.
   - Ichimoku Tenkan/Kijun/Span A/Span B calculation.
   - `evaluate_fujimoto_126(bars)` returning `signal`, `position_stage`, `position_units`, `score_total`, `score_details`, `blocking_conditions`, and order-block flags.
   - `simulate_fujimoto_126_trade(bars)` returning entry/exit times, prices, return after fee/slippage, and order-block flags.
2. Add deterministic unit tests first using synthetic bars only in tests.
3. Add a real-data backtester script, e.g. `scripts/backtest_fujimoto_126.py`, with two modes:
   - `stock-days`: evaluate available ka10080 stock×date rows directly; use this as condition/over-entry diagnostics, not deployability evidence.
   - `signals`: replay existing `trading_signals` BUY rows on the **next available minute trading day** from `intraday_prices`; this is closer to operational validation.
4. Add a missing-minute diagnostic script when `signals` mode evaluates too few trades.
5. Add static PNG chart generation for representative winning/losing trades.

## RSI pitfall in 1-2-6 staging

Do not evaluate RSI only on the final confirmation bar. In 1-2-6 interpretation:

```text
RSI recovery = early stage-1 trigger
MACD = later stage-2 confirmation
Ichimoku = later stage-3 confirmation
```

By the time MACD/Ichimoku confirm, final RSI may already be high. Detect a **recent RSI recovery event** within a lookback window, e.g.:

```text
any(prev <= 30 < curr)  # oversold recovery
or any(prev < 45 <= curr <= 75)  # intraday trend recovery band
```

Then separately record overheating as a blocking/risk condition if latest RSI is extreme (for example `>=90`), instead of erasing the earlier stage-1 event.

## Signals-mode next-day lookup

For a daily BUY `signal_date`, never replay same-day minute bars. Find the next tradable ka10080 minute day from `intraday_prices`:

```sql
select min((timestamp at time zone 'Asia/Seoul')::date)
from intraday_prices
where stock_code = :stock_code
  and source = 'kiwoom_ka10080_minute'
  and time_frame = '1min'
  and (timestamp at time zone 'Asia/Seoul')::date > :signal_day;
```

If no next day exists, record:

```text
next_trading_day_ka10080_minute_missing
```

and diagnose collection coverage. Do not treat missing minute rows as a strategy failure.

## Interpreting stock-days vs signals mode

- `stock-days` mode can show whether the filter over-enters when applied to arbitrary stored minute days. If entry rate is near 100% and average return is negative, treat it as a **filter selectivity problem** or missing candidate-quality inputs.
- `signals` mode is the preferred operational validation because it uses existing daily BUY candidates and replays the next trading day.
- If `signals` mode has only a few evaluated rows because most BUY candidates lack next-day ka10080 rows, the next step is data backfill, not strategy tuning.

## Required report shape

Return a Korean staged report with:

- completed / pending / blocker summary
- evaluated rows, entries, blocked count, entry rate
- average net return, positive rate, min/max return
- exit reason counts
- blocking condition counts
- missing ka10080 codes when applicable
- links to representative 1-minute PNG charts
- explicit safety conclusion: paper/real remain blocked

## Example commands

```bash
uv run --with pytest pytest tests/test_fujimoto_126_filter.py tests/test_entry_variant_comparison.py -q

uv run --with 'psycopg[binary]' python scripts/backtest_fujimoto_126.py \
  --mode stock-days \
  --stock-day-limit 100 \
  --json-out reports/fujimoto_126_backtest_stockdays_100.json \
  --md-out reports/fujimoto_126_backtest_stockdays_100.md

uv run --with 'psycopg[binary]' python scripts/backtest_fujimoto_126.py \
  --mode signals \
  --limit-per-date 100 \
  --json-out reports/fujimoto_126_backtest_signals_full.json \
  --md-out reports/fujimoto_126_backtest_signals_full.md
```

## Safety interpretation rule

Even if a small signals sample is positive, do **not** recommend paper/real transition when:

- evaluated trade count is under 10,
- next-day minute data coverage is incomplete,
- `stock-days` mode average net return is negative,
- `candidate_quality_external_data_not_supplied` appears on all results,
- or representative charts have not been visually inspected.

## Data Availability Checks

Before trusting backtest results, always verify that sufficient intraday data exists for the period being tested:

1. **Check intraday data availability for target dates**:
   ```python
   # For each stock/date in backtest, verify minute-bar data exists
   bars = fetch_bars_for_day(sb, stock_code, kst_date)
   if not bars:
       # Handle missing data - either skip or flag for investigation
       return {"ok": False, "blocking_conditions": ["missing_intraday_bars"]}
   ```

2. **Understand data anomalies**:
   - The 15:30 bar often shows anomalously high volume as it may represent cumulative daily volume rather than just that minute's volume
   - Always verify volume patterns look reasonable (typically 1k-100k shares per minute for active stocks, not millions)
   - If volume seems impossibly high, check if it's cumulative and adjust interpretation accordingly

3. **When minute-level data is missing**:
   - Do not trust intraday-based backtest results
   - Consider falling back to daily data analysis with appropriate caveats
   - Flag the missing data as a blocker for paper/real trading until data collection is fixed
   - Use `missing_intraday_bars` in blocking_conditions to prevent order execution

4. **Validate data collection pipelines**:
   - Regularly run checks like `check_recent_date.py` to ensure data is being collected for recent dates
   - Verify that collection scripts are storing data with correct `source` and `time_frame` values
   - Check for gaps in minute-bar sequences (expect ~390 bars for 09:00-15:30 KST trading session)
