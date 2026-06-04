# Daily n8n Workflow Runner Pattern

Use this when turning a timeboxed trading operating plan into runnable n8n/Python stages.

## Core pattern

1. Keep n8n as orchestration only: Cron, Execute Command, IF branching, retry, Telegram/Webhook alerts.
2. Put trading logic in versioned Python scripts under `/home/june/trading/scripts/` and pure logic in `core/`.
3. Make every stage emit the same JSON shape to stdout so n8n can branch consistently.
4. Never fake market/account data to make a stage pass. If real Kiwoom/OpenDART/Supabase data or a script is missing, return `status="blocked"` with explicit `blocking_conditions`.
5. Do not let opening-strategy stages place orders until market-hours minute-bar validation and 90-day intraday backtests pass.

## Standard JSON contract

```json
{
  "ok": false,
  "workflow": "daily_trading_workflow_v1",
  "stage": "opening_30m_standard_layer",
  "status": "blocked",
  "started_at": "...",
  "finished_at": "...",
  "model_grade": "low",
  "steps": [],
  "summary": {},
  "alerts": [],
  "blocking_conditions": [],
  "next_actions": []
}
```

Critical rule: if `blocking_conditions` is non-empty, set `ok=false` and `status="blocked"`. This prevents n8n from accidentally routing to downstream order workflows.

## Stage runner shape

Use a single command entrypoint for n8n Execute Command nodes:

```bash
cd /home/june/trading
python3 scripts/run_daily_workflow_stage.py --stage <stage_name>
```

Recommended stages:

```text
system_health_check
news_briefing_growth_analysis
stock_morning_signals
stock_trading_daily_workflow
premarket_account_risk_check
candidate_compression_layer
morning_investment_layer
opening_10m_aggressive_layer
opening_30m_standard_layer
post_opening_monitoring
midday_position_review
pre_close_risk_review
evening_selloff_layer
aftermarket_multi_timeframe_collection
stock_nightly_collection
daily_pnl_feedback_report
strategy_review_if_needed
```

## Timeboxed schedule

| Time | Stage | Rule |
|---|---|---|
| 06:50 | `system_health_check` | Check env presence and API smoke; hide secret values. |
| 07:00 | `news_briefing_growth_analysis` | News/growth briefing; heavy analysis allowed pre-market. |
| 07:30 | `stock_morning_signals` | Generate pre-market candidates from finalized data. |
| 08:00 | `stock_trading_daily_workflow` | ETL/indicators/signals/order-check report. |
| 08:30 | `premarket_account_risk_check` | Account/risk check, e.g. Kiwoom `kt00004` pattern. |
| 08:45 | `candidate_compression_layer` | Compress to TOP 5~10 real-time watch candidates. |
| 09:00 | `morning_investment_layer` | Observation only; no immediate buy at open. |
| 09:10 | `opening_10m_aggressive_layer` | OR10 alert/mock candidate only. |
| 09:30 | `opening_30m_standard_layer` | OR30 standard candidate only until validation passes. |
| 15:00 | `evening_selloff_layer` | Selloff/risk reduction; initially alert/approval mode. |
| 15:40 | `stock_nightly_collection` | OHLCV validation and collection for next day. |
| 16:10 | `daily_pnl_feedback_report` | Daily PnL, signal-vs-execution, failure reason report. |

## Daily PnL feedback report

Create a `daily_pnl_feedback_report.py`-style script that queries real `positions`, `orders`, and `trading_signals` from Supabase REST using service-role credentials from `.env` without printing values. It should report:

- open position count
- unrealized/realized PnL aggregates
- today order counts/statuses
- today signal counts and executed-signal count
- recent orders/signals
- `blocking_conditions` if tables/data are missing
- feedback questions for next strategy iteration

Do not store daily PnL details in durable memory. Store logs in DB/reports/session. Only reusable lessons go to skill or compact memory.

## Telegram/n8n alerting

After importing a draft n8n workflow, wire Telegram credentials manually in n8n **or** use the Docker `trading-runner` notification path when n8n cannot safely execute host Python directly. See `references/n8n-docker-runner-ops.md` for the Docker runner, import, activation, and alert-spam guard procedure.

Send only:

```text
stage
ok/status
summary
alerts
blocking_conditions
next_actions
```

Never include API keys, account numbers, PATs, DATABASE_URL, or service-role keys in stdout or alerts.

For high-frequency intraday stages, default to `notify=false` until conditional alerting exists. In particular, 5-minute snapshot/timing scans should write execution history but not spam Telegram on every blocked or empty-watchlist run.

## Safety gates for opening strategy

For `opening_multi_factor_v1`:

- `09:10` runs `scripts/run_opening_strategy_research.py --stock-code 005930 --limit-bars 10` initially.
- `09:30` runs the same script with `--limit-bars 30`.
- Add blocking conditions such as `pattern_model_not_ready_for_auto_order` and `ka10005_timeframe_needs_market_hours_validation` until 90-day intraday validation is complete.
- These stages are alert/mock only; Leader AI order workflow must be separate and approval-gated.
- If live market snapshots are being accumulated instead of historical minute backfill, keep 90-day backtest and order stages blocked with explicit conditions such as `verified_minute_history_api_not_available`, `snapshot_1m_accumulation_and_backtest_required`, or `insufficient_backtest_trade_count` rather than fabricating historical minute bars.
