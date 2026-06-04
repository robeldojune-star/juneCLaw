# Fujimoto 1-2-6 read-only backtester implementation pattern

Use this when turning a Fujimoto/Shigeru-style video/report into executable validation code in `/home/june/trading`.

## Scope and safety

- Implement as **read-only research/backtest code first**.
- Do not place Kiwoom orders, do not write `orders`/`positions`, and do not enable paper/real execution.
- Return explicit safety fields in all strategy outputs:
  - `paper_order_allowed=false`
  - `real_order_allowed=false`
  - `order_execution_enabled=false`
  - `blocking_conditions` includes `paper_order_blocked` and `real_order_blocked`
- Do not change `opening_multi_factor_v1` thresholds/weights/order behavior while adding the backtester.

## Recommended file shape

- Pure calculation module:
  - `core/fujimoto_126_filter.py`
  - no DB access, no network, no order APIs
- Backtest runner:
  - `scripts/backtest_fujimoto_126.py`
  - reads real Supabase/Postgres data only
  - writes JSON/Markdown reports under `reports/`
- Tests:
  - `tests/test_fujimoto_126_filter.py`

## Strategy translation

Interpret 1-2-6 as staged risk-budget units:

| Stage | Condition | Units |
|---|---|---:|
| `STAGE1` | RSI recovery | 1 |
| `STAGE2` | RSI recovery + MACD confirmation | 3 cumulative |
| `STAGE3` | RSI + MACD + Ichimoku cloud confirmation | 9 cumulative |

Machine-readable result should include:

```json
{
  "strategy": "fujimoto_126_trend_confirmation_v1",
  "signal": "HIGH_CONFIDENCE_CANDIDATE|WATCH|BLOCKED",
  "position_stage": "NONE|STAGE1|STAGE2|STAGE3",
  "position_units": 0,
  "score_total": 0,
  "score_details": {
    "rsi_recovery": {},
    "macd_confirmation": {},
    "ichimoku_confirmation": {},
    "market_regime": {},
    "candidate_quality": {},
    "risk_control": {},
    "thresholds": {}
  },
  "blocking_conditions": [],
  "paper_order_allowed": false,
  "real_order_allowed": false,
  "order_execution_enabled": false
}
```

## RSI pitfall for 1-2-6

Do not judge RSI only on the final bar. In staged 1-2-6, RSI is an early Stage1 trigger; by the time MACD and Ichimoku confirm, final RSI can already be above the ideal rebound band.

Better pattern:

- Compute RSI series.
- Detect a recent recovery event such as:
  - previous RSI `<=30` and current RSI `>30`, or
  - previous RSI `<45` and current RSI in a trend recovery band such as `45~75`.
- Mark severe overheat separately as a blocking/risk condition, but preserve evidence that the earlier RSI recovery occurred.

## Ichimoku pitfall

Ichimoku needs enough intraday bars:

- Tenkan: 9 bars
- Kijun: 26 bars
- Span B: 52 bars

If bars are insufficient, block explicitly:

```text
insufficient_intraday_bars_for_ichimoku
ichimoku_cloud_not_confirmed
```

For a stronger signal, prefer price above cloud plus Tenkan >= Kijun. If prior cloud touch/retest is detected, award higher confidence than a simple first breakout.

## Backtester data modes

Support two read-only modes:

1. `signals` mode
   - Read `trading_signals` BUY rows.
   - Replay the next available ka10080 minute trading day per stock.
   - Use this to see whether existing daily/research signals would have passed Fujimoto intraday timing.

2. `stock-days` mode
   - Directly evaluate available `intraday_prices` stock×date rows.
   - Use this as a smoke test or when `trading_signals` coverage is small.

Always filter minute data with:

```sql
source='kiwoom_ka10080_minute'
time_frame='1min'
```

Do not use `ka10005` or synthetic/sample OHLCV for this backtest.

## Report shape

Write both JSON and Markdown. Include at least:

- mode, generated time, data source/time frame
- parameters
- evaluated count, entries, blocked, entry rate
- return summary: avg/min/max/positive rate
- `exit_reason_counts`
- `stage_counts`
- `blocking_condition_counts`
- sample rows with date/code/entry/exit/net%/blocks
- interpretation warning that small samples are not strategy approval

## Verification sequence

Follow TDD:

1. Write tests for pure module behavior first.
2. Confirm RED failure before implementation.
3. Implement the pure module.
4. Run unit tests.
5. Compile changed files:
   ```bash
   python3 -m py_compile core/fujimoto_126_filter.py scripts/backtest_fujimoto_126.py tests/test_fujimoto_126_filter.py
   ```
6. Run a small real-data smoke test:
   ```bash
   uv run --with 'psycopg[binary]' python scripts/backtest_fujimoto_126.py --mode stock-days --stock-day-limit 5
   uv run --with 'psycopg[binary]' python scripts/backtest_fujimoto_126.py --mode signals --limit-per-date 5
   ```

## Interpretation rules

- If entries are fewer than 10, treat as connectivity/logic smoke, not performance evidence.
- If `signals` mode has `missing_next_day_minute_count`, inspect ka10080 coverage before changing strategy thresholds.
- If `entry_rate_pct` is unexpectedly 100% on tiny `stock-days` samples, expand the sample and chart-validate before trusting it.
- Keep paper/real blocked until backtest sample size, chart validation, and existing strategy gates pass.