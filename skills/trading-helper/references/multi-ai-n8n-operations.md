# Multi-AI + n8n Operations Blueprint

Use this when extending the trading project from scripts into multi-agent operations with n8n orchestration.

## Division of Responsibilities

- **n8n**: scheduling, workflow branching, retries, alerts, approval gates, and webhook/API orchestration.
- **Hermes main / Leader AI**: architecture review, code changes, final decision policy, Git operations, and human-facing explanations.
- **Research AI**: OpenDART financial filters, Kiwoom price/volume analysis, news/disclosure analysis, signal generation, score breakdowns.
- **Monitoring AI**: diagnose failed trades, account/position mismatches, API errors, missing signals, risk events, and alert routing.
- **Python core**: deterministic API calls, Supabase CRUD, indicator calculation, risk sizing, order execution wrappers.
- **Supabase**: source of truth for market data, indicators, signals, orders, positions, risk events, and agent run logs.

Do not put strategy math, order sizing, or complex signal logic directly in n8n Function nodes. Keep those in versioned Python modules and let n8n call scripts or HTTP endpoints.

## Recommended Workflow Set

1. **Pre-market check** around 08:30
   - Kiwoom smoke test
   - OpenDART smoke test
   - kt00004 account check
   - universe/table health check
   - alert summary

2. **Daily data pipeline** after market close
   - collect KOSPI universe
   - collect daily Kiwoom prices
   - validate Samsung/KRX price quality
   - only then calculate technical indicators

3. **Research signal generation** after data pipeline passes
   - calculate indicators if needed
   - generate daily BUY/SELL/HOLD
   - include score_details and blocking_conditions
   - store to trading_signals and notify summary

4. **Intraday monitoring** every 5–10 minutes during market hours
   - kt00004 account snapshot
   - compare Kiwoom holdings vs DB positions
   - detect order failures, risk thresholds, missing fills, stale data
   - alert only actionable anomalies

5. **Order approval / execution**
   - first phase should be mock + approval-gated
   - create order_candidates
   - risk check before order
   - Telegram/manual approval before Kiwoom order
   - only consider fully automatic mode after 2–4 weeks stable mock logs

## Standard stdout Contract for n8n-called Scripts

Every `scripts/run_*.py` entrypoint should print human-readable logs if useful, but the final line should be JSON:

```json
{
  "ok": true,
  "workflow": "premarket_check",
  "steps": [
    {"name": "kiwoom_smoke", "ok": true},
    {"name": "opendart_smoke", "ok": true},
    {"name": "account_check", "ok": true}
  ],
  "alerts": [],
  "next_action": "none"
}
```

Failure example:

```json
{
  "ok": false,
  "workflow": "daily_data_pipeline",
  "steps": [
    {"name": "collect_daily_prices", "ok": true},
    {"name": "validate_samsung", "ok": false, "error": "KRX close ratio mismatch"}
  ],
  "alerts": ["Stop indicator/signal generation until price validation passes"],
  "next_action": "alert_and_stop"
}
```

n8n should branch on `ok`, `steps[*].ok`, and `next_action`, not scrape free-form logs.

## Suggested Project Structure

```text
core/
  database.py
  signal_service.py
  financial_service.py
  risk_service.py
  order_service.py
  monitoring_service.py
ai_agents/
  research_ai.py
  monitoring_ai.py
  leader_ai.py
scripts/
  run_premarket_check.py
  run_daily_data_pipeline.py
  run_research_ai.py
  run_monitoring_ai.py
  run_leader_ai.py
workflows/n8n/
  README.md
  01_premarket_check.json
  02_daily_data_pipeline.json
  03_research_signals.json
  04_intraday_monitoring.json
  05_order_approval.json
```

## Supabase Tables to Add When Needed

- `agent_runs`: workflow/agent execution history, status, input/output summaries, errors.
- `risk_events`: risk alerts, failure diagnostics, severity, stock_code, raw payload.
- `order_candidates`: pre-order approval queue with risk result and status.
- `financial_scores`: OpenDART-derived financial factor scores and flags.

## Implementation Order

1. Add `core/database.py` and common connection helpers.
2. Add `core/workflow_result.py` or equivalent JSON result helper.
3. Add `scripts/run_premarket_check.py`.
4. Add `scripts/run_daily_data_pipeline.py`.
5. Add `workflows/n8n/README.md` documenting required commands/env.
6. Then split Research AI, Monitoring AI, and Leader AI.
7. Only after stable mock operations, add order approval and mock order execution.

## Safety Rules

- Real market data only: Kiwoom/OpenDART/Supabase; no fake market rows.
- Do not let n8n contain secret literals; use environment/credential store.
- Do not let n8n contain strategy logic; use Python modules.
- No production trading until mock mode has stable logs, order failure diagnosis, account/DB reconciliation, and alerting.
- Strategy threshold or weight changes must be reviewed separately from infrastructure changes.
