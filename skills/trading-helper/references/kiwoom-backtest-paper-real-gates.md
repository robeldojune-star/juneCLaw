# Kiwoom backtest → paper → real-pilot gates

Use this reference for trading-system work that spans historical data collection, strategy validation, paper/simulated execution, and real-money pilot design.

## Core operating split

Do **not** run Kiwoom mock/prod by mutating a global `TRADING_ENV` on a clock schedule. Declare the intended environment per task:

| Task class | Kiwoom env | Order side effects | Notes |
|---|---|---:|---|
| Historical 1-minute collection | `mock`/backtest credentials | none | `ka10080`, `source=kiwoom_ka10080_minute`, `time_frame=1min` |
| Backtest | DB only | none | no Kiwoom calls required after data is stored |
| Live observation | `prod` | none | current-session `ka10006 snapshot_1m`, account read-only checks |
| Paper/simulated ledger | mock or DB-only | no Kiwoom order API | write `orders.status=SIMULATED` only |
| Real pilot | `prod` | only after explicit multi-key gate | never create cron-based real-order automation by default |

Recommended guard shape:

```text
REAL_ORDER_ENABLED=true
USER_CONFIRMED_REAL_ORDER=true
READINESS_REAL_ORDER_GATE=true
kiwoom_env=prod
```

All must be true before any future real-order executor may call Kiwoom order APIs.

## `ka10080` data eligibility for OR10/OR30

Rows alone are insufficient. Filter by stock×date before backtesting:

```text
source == kiwoom_ka10080_minute
time_frame == 1min
09:00~09:30 all minute bars present
opening duplicate minutes == 0
OHLC structure valid
```

Partial days where the first bar is 10:22 or 13:06 must be excluded from OR10/OR30 tests, even if the total row count is high.

Typical backtest arguments:

```bash
python3 scripts/backtest_opening_strategy.py \
  --stock-codes 005930 000660 035420 005380 068270 \
  --days 130 \
  --time-frame 1min \
  --source kiwoom_ka10080_minute \
  --eligible-opening-only \
  --fee-bps 23 \
  --slippage-bps 10
```

Interpretation gate:

```text
rows/trades pass is not enough.
If avg_return_pct <= 0 after fees/slippage, paper and real remain blocked.
```

## Paper ledger must model real friction

Paper/simulated orders should store conservative execution assumptions, not just the signal price:

```text
reference_signal_price
assumed_fill_price
fee_bps_one_way
slippage_bps_one_way
impact_bps_one_way
estimated_fee
estimated_cash_effect
mode = paper_only_no_kiwoom_order_api
```

Use this to measure whether a strategy still has positive expectancy after costs. Mock fills do not create real market impact, so paper must be conservative.

## Real pilot is for execution quality, not profit maximization

For an account under 1,000,000 KRW, initial pilot should be tiny and manual/approved:

```text
total pilot budget <= 100,000 KRW
per order <= 20,000~30,000 KRW
max real orders/day <= 1~3
market orders disabled
limit orders only at first
```

Record execution-quality fields before evaluating strategy profit:

```text
signal_to_order_latency_ms
order_ack_latency_ms
requested_price
avg_fill_price
filled_qty / unfilled_qty
partial_fill flag
slippage_bps
post_entry_1m/3m/5m_return
paper_vs_real_return_gap
```

Real pilot progression:

```text
Phase 0: shadow mode, no order
Phase 1: manual one-click order by user, system records only
Phase 2: approved API order candidate, executor still requires explicit user approval before implementation
```
