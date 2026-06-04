# Morning news briefing + historical snapshot replay operations

Use this reference when the user asks to connect 07:00 news briefing templates, `ka10006 snapshot_1m` integrity checks, OR10/OR30 opening loops, or whether in-progress opening strategy gates can be checked with historical data.

## 1. Morning news briefing as pre-market input, not an order signal

The user's sample morning briefing prompt has three repeated news-type runs:

| News type | Scope | Purpose |
|---|---|---|
| 글로벌이슈 | US market, China policy, FX, commodities, geopolitical risk | Infer domestic market direction and beneficiary/damage sectors |
| 기업공시 | earnings, large contracts, M&A, capital increases, buybacks, executive changes | Identify stock-specific catalysts |
| 테마급등 | SNS/community themes, surging themes, suspicious momentum, volume spikes | Separate short-term flow candidates from risky hype |

Operational rule:

```text
07:00 news_briefing_growth_analysis
  -> news/disclosure/theme candidates
  -> stock_morning_signals
  -> candidate_compression_layer / today_watchlist
  -> OR10/OR30 snapshot_1m revalidation
```

Do **not** treat the briefing as a buy order. It is only an input to candidate compression. Before any order path, the candidate must pass the current trading gates: `snapshot_1m` quality, OR10/OR30 `score_details`, explicit `blocking_conditions`, backtest readiness, paper review, and user approval.

The briefing output should include:

- headline and 1-2 line summary
- beneficiary stock and code
- news -> stock linkage reason
- latest/current price source and timestamp, preferably broker/Kiwoom-confirmed before trading
- expected impact strength
- tactical view: open-buy / pullback-watch / watch / avoid
- risks and explicit `order_allowed=false`

## 2. Historical checking: what is allowed

When the user asks whether an in-progress `ka10006 snapshot_1m` gate can be checked with past data, answer yes with clear separation:

| Stage | Historical check possible? | Notes |
|---|---:|---|
| `ka10006 snapshot_1m` integrity | Yes | Use already accumulated `intraday_prices(source=kiwoom_ka10006_snapshot,time_frame=snapshot_1m)` for rows, active codes, duplicate keys, OHLC quality, latest timestamp. |
| OR10/OR30 opening loops | Partially | Historical replay/backtest can recompute opening range candidates and `score_details`; real-time lag, actual alert timing, and live API reliability still require market-hours validation. |
| 15:00/15:40 collection + PnL report | Partially | Works if historical signal/order/report rows exist; blocked/no-signal output is valid when no orders/signals exist. |
| paper-only loop | Not until gates pass | Do not enable paper orders merely because a historical replay runs. Require rows/trades and quality gates. |

Allowed data:

```text
- accumulated real ka10006 snapshot_1m rows
- verified Kiwoom/OpenDART/Supabase data
- verified separate minute-history API if later identified
```

Forbidden data:

```text
- ka10005 date-only responses treated as 1-minute bars
- synthetic/random/sample OHLCV to pass a gate
- lowering rows/trades thresholds just to unblock paper/real orders
```

## 3. Current safe command pattern

Snapshot integrity:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/inspect_snapshot_1m_status.py --days 2 --min-rows 20
```

Backtest/replay readiness with accumulated `snapshot_1m`:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage backtest_opening_strategy_90d --pretty
```

Readiness gate:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/check_backtest_readiness.py
```

Interpretation example:

```text
rows_used < min_rows_required or total_variant_trades < min_trades_required
=> status=blocked is correct
=> this is data accumulation/readiness, not permission to paper/real order
```

## 4. Recommended future replay diagnostic

If the user wants stronger historical validation of stages 5-6, add a replay diagnostic rather than weakening gates:

```text
historical snapshot_1m replay
  -> group rows by stock_code + KST trading date
  -> cut rows to the 09:10 window and run OR10 evaluation
  -> cut rows to the 09:30 window and run OR30 evaluation
  -> emit the same candidate `score_details` and `blocking_conditions` used by live stages
  -> compare later-day path/close only for research metrics
  -> keep `order_execution_enabled=false`
```

The replay output should be a JSON envelope compatible with n8n/Hermes stages and must keep `paper_order_allowed=false` and `real_order_allowed=false` until readiness and approval gates pass.

## 5. Reporting style for this user

When explaining historical checks, be concise and concrete:

1. State whether it is possible.
2. Show which stages are fully/partially checkable.
3. Run or cite the real readiness command if appropriate.
4. Report `rows_used`, `min_rows_required`, `total_variant_trades`, `min_trades_required`, and blocking conditions.
5. Reaffirm that `ka10005` minute-like backfill and fake data are prohibited.
