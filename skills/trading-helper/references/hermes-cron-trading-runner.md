# Hermes cron + trading-runner no-n8n pattern

Use this when n8n workflow/API/credential/import handling becomes too complex for a simple recurring trading operation. The user's preference is to simplify: keep n8n optional/back-up and run the stable Python stage directly through `trading-runner`.

## Trigger conditions
- User says n8n is too complex or asks to do it "without n8n".
- The task is a simple recurring trading stage, especially data collection or health checks.
- Docker n8n can call `trading-runner`, but the orchestration adds more complexity than value.

## Standard shape

```text
Hermes cron (no_agent=true)
  -> ~/.hermes/scripts/<watchdog>.py
      -> docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
         python scripts/run_daily_workflow_stage.py --stage <allowed_stage>
      -> optional read-only quality gate, e.g.
         python scripts/inspect_snapshot_1m_status.py --days 2 --min-rows 20 --min-codes 5 --max-lag-minutes 20
```

For `ka10006` snapshot collection, prefer a two-step watchdog: collect first, then immediately run a read-only integrity inspector. This catches silent data-quality drift while keeping normal/off-hours runs quiet.

## Watchdog script behavior
- Put the script under `~/.hermes/scripts/` and register it by relative filename in `cronjob`.
- Use `no_agent=true` for deterministic script-only runs.
- Make success/off-hours silent: empty stdout means no delivery.
- Print a concise alert and exit non-zero only on runner error, invalid JSON, blocked/failed/error status, integrity-check `blocking_conditions`, or unexpected quality alerts.
- Include KST market-window gating inside the script, not just in the cron expression, to survive scheduler timezone differences.
- Never print secrets; read project env indirectly through the runner/project code.
- Parse JSON from each runner command. Treat empty stdout, non-object JSON, or JSONDecodeError as alert-worthy because no-agent cron otherwise hides malformed stage output.
- For early `snapshot_1m` accumulation, do not treat simple data scarcity as permission to bypass gates. Scarcity should keep backtest/order stages blocked while collection continues.

## Example schedule

```python
cronjob(
  action="create",
  name="trading-snapshot-1m-collector-no-n8n",
  schedule="*/5 * * * *",
  script="trading_snapshot_collector.py",
  no_agent=True,
  workdir="/home/june/trading",
  enabled_toolsets=["terminal"],
)
```

## n8n duplicate-call guard
If replacing an active n8n workflow, disable it before enabling Hermes cron to avoid duplicate trading-runner calls:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T n8n \
  n8n update:workflow --id=daily_trading_workflow_v1 --active=false
# or, on newer n8n, use unpublish:workflow if available

docker compose -f /home/june/n8n/docker-compose.yml restart n8n worker
```

Verify with Postgres DB or n8n CLI that `active=false`, then test the runner directly.

## Verification checklist
1. `docker ps` shows `n8n-trading-runner-1` healthy/up.
2. `run_daily_workflow_stage.py --stage system_health_check` returns `ok=true`.
3. The target collection stage returns JSON with `ok=true`, `status=completed`, and no blocking conditions.
4. Run the integrity inspector from inside `trading-runner`; for snapshot collection expect `ok=true`, enough rows/codes for the current phase, `duplicate_stock_timestamp_keys=0`, empty `quality_error_counts`, and acceptable `latest_lag_minutes`.
5. Relevant Supabase rows use the exact expected identifiers, e.g. `source=kiwoom_ka10006_snapshot` and `time_frame=snapshot_1m`.
6. `cronjob(action="list")` shows `last_status=ok` after a manual `cronjob(action="run")` or first scheduled run.
7. Run `python3 -m py_compile` on any host-side watchdog and edited project scripts; inside containers, prefer the same `python` executable used by `trading-runner`.

## Daily report integration
When closing Phase 1/2 collection stabilization, add snapshot accumulation status to `daily_pnl_feedback_report` rather than only checking it ad hoc. Include:
- source/time_frame
- lookback days
- row count and active code count
- latest timestamp and lag minutes
- duplicate `(stock_code,timestamp)` count
- OHLC/timestamp quality error counts
- snapshot-specific blocking conditions

Treat snapshot query/quality/timestamp failures as hard report blockers. Treat early row-count scarcity as an explicit accumulation status, not as permission to proceed to paper/real orders.

## OR10/OR30 and backtest gates
For opening-layer verification, inspect both code path and runtime output:
- `opening_10m_aggressive_layer` and `opening_30m_standard_layer` should collect current snapshots first, then call the candidate loop.
- The bar loader must filter Supabase by `time_frame=eq.snapshot_1m` and `source=eq.kiwoom_ka10006_snapshot`; do not fall back to `ka10005` minute data.
- Empty candidates should yield `opening_candidate_list_empty` / `no_opening_buy_candidates`, not sample tickers.
- Auto-order guards must remain blocked with `snapshot_1m_accumulation_and_backtest_required` until accumulated rows/trades pass the backtest readiness gate.
- `backtest_opening_strategy_90d` should run with `--time-frame snapshot_1m`; if rows/trades are below thresholds, `insufficient_intraday_rows_for_backtest` and/or `insufficient_backtest_trade_count` are the correct result.

## Trading-specific safety
- For `ka10006` snapshot accumulation, store rows as `intraday_prices.time_frame=snapshot_1m` and `source=kiwoom_ka10006_snapshot`.
- Keep real ordering/auto-order stages blocked until enough `snapshot_1m` data accumulates and backtests pass.
- Do not re-enable real order execution just because the collector works.
