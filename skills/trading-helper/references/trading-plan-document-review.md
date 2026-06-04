# Trading plan document review and alignment

Use this when the user asks to review stored plans, strategy docs, or workflow docs in `/home/june/trading` and check whether the direction still matches current operations.

## Current source-of-truth pattern
Treat the latest operational plan and live state as higher priority than older strategy drafts. In this project, stale docs often preserve earlier assumptions even when the code/ops path has changed.

Current canonical direction learned from the ka10005 → ka10006 transition:

```text
Real data only
ka10005 date-only/daily-like responses are not minute bars
ka10006 current-session snapshots are accumulated as intraday_prices snapshot_1m
Hermes cron + trading-runner is the primary simple collection path
n8n is optional/backup unless explicitly re-enabled
Auto/real orders stay blocked until snapshot_1m accumulation and backtests pass
```

## Review sequence
1. Inventory saved planning artifacts before editing or implementing:
   - `docs/strategies/*.md`
   - `docs/strategies/*.json`
   - `workflows/n8n/*.md`
   - `workflows/n8n/*.json`
   - `.hermes/plans/*.md`
2. Identify the latest/current plan document first. Prefer it as the baseline when it reflects live operations.
3. Compare older docs against the baseline and classify each as:
   - still directionally valid
   - valid but needs terminology update
   - stale/backup-only
   - unsafe if followed literally
4. Specifically scan for stale assumptions:
   - `ka10005` as a minute/intraday source
   - `ka10005_timeframe_needs_market_hours_validation` as the main blocker after ka10005 has already been rejected
   - n8n as the primary scheduler when Hermes cron has replaced it
   - BUY/Strong BUY flowing directly into order execution before paper/backtest gates
5. Report direction first, then propose doc patches. Do not continue implementation when the user asked for document review.

## Recommended wording updates
Replace old ka10005 wording:

```text
Kiwoom ka10005 validation / ka10005 minute candidate
```

with:

```text
ka10005 is disabled as a minute source; use ka10006 snapshot_1m accumulation until a verified minute-history API is identified.
```

Replace old order blocker:

```text
ka10005_timeframe_needs_market_hours_validation
```

with one or more of:

```text
snapshot_1m_accumulation_and_backtest_required
verified_minute_history_api_not_available
need_90_trading_days_intraday_prices
insufficient_intraday_rows_for_backtest
insufficient_backtest_trade_count
```

Replace n8n-primary wording:

```text
n8n schedules/runs the trading workflow
```

with:

```text
Hermes cron + trading-runner is the primary simple runner; n8n remains optional backup/approval UI unless explicitly re-enabled.
```

## Pitfalls
- Do not treat every older strategy draft as wrong: many still contain valid thresholds, score breakdowns, and safety principles.
- Do not rewrite thresholds just because the orchestration changed; thresholds need backtest evidence.
- Do not record one-off review results in memory. If a repeated review method emerged, keep it here as a skill reference.
- If asked to update docs, patch the authoritative/current docs first, then older stale docs in priority order.
