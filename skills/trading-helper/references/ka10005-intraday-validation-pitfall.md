# ka10005 intraday validation pitfall

## Trigger
Use this when extending daily/n8n workflows, opening strategies, 90-day intraday collection, or Leader approval flows that depend on minute bars.

## Durable lesson
`ka10005` is labeled `주식일주월시분요청`, but a structurally valid response is not necessarily minute data. In the 2026-05-29 workflow validation, `ka10005` returned 30 OHLCV rows with date-only fields, no explicit intraday time, and only one row for the current day during market hours. Treating those rows as `1min` data polluted `intraday_prices` and made a zero-trade backtest appear successful.

## Required validation before storing as 1min
A response may be used as minute/intraday data only when all checks pass:

1. Extract time only from explicit time-like fields such as `time`, `tm`, `trde_tm`, `cntr_tm`, `stck_cntg_hour`, or combined datetime in `dt`.
2. Never treat an 8-digit `date=YYYYMMDD` as HHMMSS.
3. Require enough explicit-time rows for the requested timeframe, e.g. `explicit_time_bar_count >= min_bars`.
4. During market hours, require same-day density, e.g. `today_bar_count >= 10` for 1-minute-like data.
5. If these fail, emit blocking condition such as `ka10005_timeframe_not_minute_like` and do not upsert rows into `intraday_prices` as `time_frame=1min`.

## Collection guard
`collect_intraday_90d.py`-style collectors must block instead of inserting when `ka10005` looks daily:

- `attempted_rows` should remain 0.
- Add `ka10005_timeframe_not_validated_for_intraday_collection` or equivalent.
- Do not synthesize a `15:30` timestamp to make date-only rows fit the intraday schema.

## Backtest guard
Opening-range/intraday backtests must not report success merely because a query returned rows. Require both:

- enough rows, e.g. `min_rows >= 300` for a preliminary smoke threshold; and
- enough simulated trades, e.g. `min_trades >= 5`.

If `rows_used` is small or total trades are 0, return blocked conditions such as:

- `need_90_trading_days_intraday_prices`
- `insufficient_intraday_rows_for_backtest`
- `insufficient_backtest_trade_count`

## Cleanup pattern for polluted rows
If date-only `ka10005` rows were previously stored as 1-minute bars, remove only the targeted synthetic rows:

- `source = 'kiwoom_ka10005'`
- `time_frame = '1min'`
- timestamp corresponds to the synthetic market-close bucket, e.g. `(timestamp at time zone 'Asia/Seoul')::time = time '15:30:00'`

Use a dry run first, show row counts and a small sample, then apply deletion. Do not delete other sources or rows with explicit intraday times.

## n8n workflow implication
Keep these stages as blocking/guard stages until real minute data is proven:

- `ka10005_timeframe_validation`
- `collect_intraday_90d`
- `backtest_opening_strategy_90d`
- `simulate_approved_orders`

Leader approval/order workflows must remain paper-only or blocked while the minute-data and 90-day backtest guards are active.
