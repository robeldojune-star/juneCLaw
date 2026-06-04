# Next trading day intraday operational gate

Use this when resuming the `/home/june/trading` trading system after a weekend/holiday/off-hours period while the current plan is based on `ka10006` `snapshot_1m` accumulation.

## Core rule

Do not interpret off-hours/holiday/weekend `latest_timestamp_stale` as a collector failure. During the next real trading session, verify live quality with fresh `lag / rows / active_codes` before changing code or schedules.

## Required sequence

1. Keep `snapshot_1m` accumulation running via Hermes cron/trading-runner.
2. During the next real market session, check snapshot quality:
   ```bash
   docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
     python scripts/inspect_snapshot_1m_status.py --days 2 --min-rows 20
   ```
   Confirm:
   - `source=kiwoom_ka10006_snapshot`
   - `time_frame=snapshot_1m`
   - rows increasing during the session
   - `active_codes` at least 5, preferably 10+
   - no duplicate stock/timestamp keys
   - `quality_error_counts={}`
   - live-session lag is not much larger than the collection interval
3. Verify OR candidate loops still emit per-candidate score breakdowns and keep order guards disabled:
   ```bash
   docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
     python scripts/run_daily_workflow_stage.py --stage opening_10m_aggressive_layer --pretty
   docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
     python scripts/run_daily_workflow_stage.py --stage opening_30m_standard_layer --pretty
   ```
   Check `candidate_count`, `evaluated_count`, candidate `score_details`, `blocking_conditions`, and `order_execution_enabled=false`.
4. Check readiness before any paper/real order path:
   ```bash
   docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
     python scripts/check_backtest_readiness.py
   ```
   Keep orders blocked until `snapshot_quality_ok`, `backtest_rows_ok`, and `backtest_trades_ok` are all true.
5. If `signal=0` recurs on the next trading day, diagnose before changing strategy:
   - missing daily/indicator data
   - UTC/KST date filter or latest batch query
   - threshold too strict (do not change without backtest/user approval)
   - real market conditions produced no candidates

## Explicit order gate

Until rows/trades readiness passes and the user explicitly approves:

```json
{
  "paper_order_allowed": false,
  "real_order_allowed": false,
  "order_execution_enabled": false
}
```

## Project runbook

The project-level runbook created from this pattern lives at:

`/home/june/trading/docs/strategies/next_trading_day_intraday_operational_gate.md`
