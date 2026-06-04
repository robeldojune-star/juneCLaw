# Kiwoom backtest data, mock/prod mode separation, and rollout gates

Use this reference when operating the `/home/june/trading` Kiwoom + Supabase trading pipeline.

## Core lesson

Do **not** treat mock/prod as a time-based global toggle. Treat each operation as a separate execution purpose with an explicit Kiwoom environment and side-effect envelope.

```text
Historical backtest data collection -> mock + ka10080, no orders
Backtest computation                -> DB only, no Kiwoom calls, no orders
Live/current-session observation    -> prod + ka10006 snapshot, no orders
Paper/simulated test                -> DB ledger/orders.status=SIMULATED, no Kiwoom real order API
Real pilot                          -> prod only, separate executor, multi-key/user gate required
```

Avoid cron jobs that mutate `.env`/`TRADING_ENV` by time of day. Cron jobs should call scripts that pass `--trading-env mock` or `--trading-env prod` explicitly.

## Data source split

| Purpose | API | Kiwoom env | DB source | time_frame |
|---|---|---|---|---|
| Historical 1-minute backtest bars | `ka10080 주식분봉차트조회요청` | usually `mock` | `kiwoom_ka10080_minute` | `1min` |
| Current-session live observation | `ka10006` snapshot | usually `prod` | `kiwoom_ka10006_snapshot` | `snapshot_1m` |
| Deprecated/unsafe minute source | `ka10005` date-like rows | n/a | do not use | do not use |

`ka10080` lives under `/api/dostk/chart`, uses `tic_scope='1'`, and returns minute timestamps in `cntr_tm` under `stk_min_pole_chart_qry`.

## Integrity checks before using ka10080 in OR10/OR30 backtests

Rows alone are not enough. Check both numeric integrity and chart/coverage shape.

Minimum per stock×date eligibility for OR10/OR30:

```text
source == kiwoom_ka10080_minute
time_frame == 1min
(stock_code, timestamp) duplicate count == 0
OHLC is structurally valid: high >= open/close and low <= open/close
09:00~09:30 opening coverage is complete
partial days are excluded or recollected
```

Treat 15:21~15:29 as a special closing call-auction gap; missing bars there are not automatically fatal for opening strategy backtests.

Useful project scripts:

```bash
python3 scripts/inspect_ka10080_minute_integrity.py
python3 scripts/create_ka10080_minute_quality_chart.py --stock-code 005930 --limit 3000 --out reports/ka10080_minute_quality_005930.html
```

## Rollout sequence

```text
1. Collect ka10080 historical bars in mock/backtest mode.
2. Verify integrity and visually inspect coverage heatmaps.
3. Backtest only eligible complete opening days.
4. Review strategy performance; rows/trades passing is not enough if avg_return_pct <= 0.
5. Run paper/simulated ledger only; no Kiwoom real order API.
6. If paper passes, design a real pilot separately.
7. For a sub-1,000,000 KRW real account, start with tiny pilot limits: <=100,000 KRW total pilot budget, <=20,000~30,000 KRW per order, <=1~3 orders/day, prefer limit orders, avoid thin liquidity.
```

## Real-vs-paper interpretation

Paper/mock fills do not create price impact. Real pilot is primarily for execution quality, not immediate profit maximization. Track:

- signal-to-order latency
- limit-order non-fill rate
- partial fills
- entry slippage vs backtest/paper entry
- immediate adverse move after entry
- fees/taxes/slippage adjusted expectancy

## Gate pattern

Real order execution should require a separate executor plus multiple explicit gates such as:

```text
REAL_ORDER_ENABLED=true
USER_CONFIRMED_REAL_ORDER=true
READINESS_REAL_ORDER_GATE=true
kiwoom_env=prod
```

Default workflows and cron jobs should remain read-only or simulation-only unless those gates are explicitly enabled by the user.
