# Daily Trading Workflow Stage Implementation Notes

Use this reference when turning the user's timeboxed multi-AI/n8n trading schedule into executable code.

## Class-level pattern

- Keep n8n as orchestration only: Cron → Execute Command → parse stdout JSON → Telegram/branching.
- Put trading logic, Supabase/Kiwoom/OpenDART calls, score calculation, and risk checks in versioned Python scripts.
- Every stage script must return a common JSON shape with:
  - `ok`
  - `workflow`
  - `stage`
  - `status`: `completed`, `blocked`, or `failed`
  - `summary`
  - `alerts`
  - `blocking_conditions`
  - `next_actions`
- Treat any non-empty `blocking_conditions` as `ok=false` and `status=blocked`. This prevents n8n from accidentally flowing into order/approval steps.
- Never fabricate market/news/account data. If the source is missing, return an explicit blocking condition.

## Recommended files in the trading repo

```text
core/workflow_result.py                      # common result dataclasses/helpers
core/supabase_rest.py                        # lightweight Supabase REST read helper, secrets hidden
scripts/run_daily_workflow_stage.py          # one entrypoint: --stage <stage_name>
scripts/news_briefing_growth_analysis.py     # morning news/growth stage; block until real collector exists
scripts/candidate_compression_layer.py       # TOP 5~10 from real trading_signals/kospi_top50
scripts/position_monitoring_stage.py         # post_opening/midday/pre_close reviews
scripts/evening_selloff_layer.py             # close/selloff review; no orders
scripts/daily_pnl_feedback_report.py         # daily PnL feedback loop
scripts/import_n8n_daily_workflow.py         # optional API import; requires N8N_API_KEY
scripts/check_telegram_connection.py         # optional Telegram env test
workflows/n8n/daily_trading_workflow_v1.import.json
```

## Stage mapping

```text
06:50 system_health_check
07:00 news_briefing_growth_analysis
07:30 stock_morning_signals
08:00 stock_trading_daily_workflow
08:30 premarket_account_risk_check
08:45 candidate_compression_layer
09:00 morning_investment_layer
09:10 opening_10m_aggressive_layer
09:30 opening_30m_standard_layer
10:00 post_opening_monitoring
11:30 midday_position_review
14:30 pre_close_risk_review
15:00 evening_selloff_layer
15:20 aftermarket_multi_timeframe_collection
15:40 stock_nightly_collection
16:10 daily_pnl_feedback_report
20:00 strategy_review_if_needed
```

## Stage implementation rules

### news_briefing_growth_analysis
- Do not summarize invented news.
- If no real RSS/news/API collector is implemented, return `news_collector_not_implemented`.
- If OpenDART key exists, a smoke check may be run, but missing keys are not a durable failure; report as a blocking condition for this run only.

### candidate_compression_layer
- Read real `trading_signals` and `kospi_top50` from Supabase.
- Compress BUY signals to TOP 5~10 before market open.
- If signals are absent, return `no_today_signals_found_for_candidate_compression`; do not create placeholder symbols.

### post_opening/midday/pre_close monitoring
- Read real `positions`, `orders`, and `trading_signals`.
- Flag pending/rejected orders, BUY signals not executed, stop-loss review, take-profit review, and pre-close day-trade hold/close decision.
- These stages observe and report; they do not place orders.

### evening_selloff_layer
- Build `review_items` for open positions with `recommended_action`.
- Always keep `order_execution_enabled=false` unless a separate Leader AI/human approval workflow is explicitly built.
- Examples of review flags: `loss_exceeds_intraday_stop_reference`, `profit_exceeds_second_take_profit_reference`, `day_trading_strategy_position`.

## n8n import and Telegram

- First check local n8n health: `/healthz` can be OK while `/rest/workflows` returns 401.
- API import requires `N8N_API_KEY`; absent key should return `missing_n8n_api_key`, not a hard failure narrative.
- Telegram can be handled through n8n credentials or env vars; absent token/chat id should return `missing_telegram_bot_token` / `missing_telegram_chat_id`.
- Keep imported workflows `active=false` until credentials and safety gates are reviewed.

## Verification checklist

```bash
python3 -m json.tool workflows/n8n/daily_trading_workflow_v1.import.json >/dev/null
python3 -m json.tool docs/strategies/strategy_registry.json >/dev/null
python3 -m py_compile core/*.py scripts/*.py

for st in candidate_compression_layer post_opening_monitoring midday_position_review pre_close_risk_review evening_selloff_layer; do
  python3 scripts/run_daily_workflow_stage.py --stage "$st" >/tmp/stage_${st}.json || test $? -eq 2
  python3 -m json.tool /tmp/stage_${st}.json >/dev/null
done
```

Before commit, scan staged diffs for real keys/account numbers. Placeholder env names like `TELEGRAM_BOT_TOKEN` are OK; actual values are not.
