# Signal events batch backtest workflow

Use this reference when implementing or operating signal-utilization analysis for the trading project: stored daily signals → auditable `signal_events` → cumulative outcome report.

## Trigger

Use this workflow when the user asks to:

- replay stored `trading_signals` across multiple `signal_date` values,
- compare `BLOCKED_ENTRY_SIGNAL` versus `INTRADAY_ENTRY_SIGNAL`,
- diagnose whether the opening layer is over-blocking daily BUY candidates,
- create cumulative reports before considering paper/real order rollout.

## Core pattern

1. Keep orders disabled. This workflow is read-only except optional `signal_events` upsert.
2. Query distinct `trading_signals.signal_date::date` values, optionally bounded by `--start-date`, `--end-date`, or `--max-dates`.
3. For each signal date, replay each stored signal into event records:
   - `DAILY_ENTRY_CANDIDATE` for daily BUY candidate signals.
   - `EXIT_SIGNAL` for stored SELL signals, even if no position exists.
   - `DAILY_HOLD_SIGNAL` for HOLD signals.
   - `INTRADAY_ENTRY_SIGNAL` when ka10080 OR10/OR30 breakout entry exists on the next available minute trading day.
   - `BLOCKED_ENTRY_SIGNAL` when the next minute day is unavailable, opening range is incomplete, or no OR breakout happens.
4. Upsert events idempotently by deleting existing rows for the same `source_signal_id` before re-inserting, unless an explicit `--keep-existing-events` mode is requested.
5. Generate JSON and Markdown reports under `reports/`, including:
   - event counts,
   - blocking-condition counts,
   - daily BUY after_1d/after_3d outcomes when daily rows exist,
   - SELL after_1d/after_3d outcomes,
   - `INTRADAY_ENTRY_SIGNAL` net return,
   - `BLOCKED_ENTRY_SIGNAL` proxy return,
   - blocked-vs-entry average return difference.

## Important no-lookahead rule

For post-close daily signals, never replay against the same day’s minute bars.

Correct next trading day lookup:

```sql
select min((timestamp at time zone 'Asia/Seoul')::date)
from intraday_prices
where stock_code = :stock_code
  and source = 'kiwoom_ka10080_minute'
  and time_frame = '1min'
  and (timestamp at time zone 'Asia/Seoul')::date > :signal_day;
```

Only use `daily_prices` next row as a fallback for older historical signals when it is strictly greater than `signal_day`. Do not fallback to the same day just because the latest daily bar has not been collected yet.

## Blocked-entry proxy return

When `BLOCKED_ENTRY_SIGNAL` is caused by `no_opening_range_breakout`, there is no actual entry price. To compare it with entries, record a proxy:

- proxy start: close of the final OR range bar (`09:10` for OR10, `09:30` for OR30),
- proxy exit: first bar at/after configured `time_exit` (usually `15:20`) or last available bar,
- metrics:
  - `blocked_proxy_return_to_time_exit_pct`,
  - `blocked_proxy_return_to_day_high_pct`,
  - `blocked_proxy_return_to_day_low_pct`.

Use this only as a diagnostic for “did blocked candidates rise anyway?” Do not treat it as a simulated executable trade.

## Interpretation rules

- If `trading_signals` has only one `signal_date`, report that the batch infrastructure is ready but the sample is insufficient.
- If `after_1d`/`after_3d` counts are zero, daily data has not accumulated yet; do not infer swing performance.
- If `blocked_entry_next_day_proxy_return` outperforms `intraday_entry_net_return`, suspect over-strict OR/opening-layer gating, but require more dates before changing thresholds.
- If `INTRADAY_ENTRY_SIGNAL` net return is negative, keep paper/real orders blocked.
- Do not change strategy weights, thresholds, or order behavior directly from this report; present evidence and ask for review.

## Verification commands

Typical local execution from `/home/june/trading`:

```bash
uv run --with 'psycopg[binary]' python3 -m py_compile \
  scripts/backtest_signal_event_outcomes.py \
  scripts/backtest_signal_event_outcomes_batch.py

uv run --with 'psycopg[binary]' python3 scripts/backtest_signal_event_outcomes_batch.py --record-events
```

Expected outputs:

```text
reports/signal_event_outcomes_batch_latest.json
reports/signal_event_outcomes_batch_latest.md
```

## Safety gates

- Never call Kiwoom order APIs from this workflow.
- Never write to `orders` or `positions`.
- `signal_events` upsert is allowed because it is audit/logging state.
- Keep paper/real order rollout blocked until cumulative rows/trades/performance gates are positive and separately approved.
