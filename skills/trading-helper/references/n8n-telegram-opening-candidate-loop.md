# n8n Telegram + opening candidate loop pattern

Use this when extending the daily trading n8n workflow after the base `run_daily_workflow_stage.py --stage ...` runner exists.

## Telegram credential pattern

- Keep project secrets out of Git and chat.
- Prefer n8n UI credentials for n8n Telegram nodes.
- For Python-side smoke tests, read `/home/june/trading/.env` first, then `~/.hermes/.env` as fallback for Hermes-level Telegram credentials.
- Accept either `TELEGRAM_CHAT_ID` or `HERMES_TELEGRAM_CHAT_ID` for direct Bot API tests.
- Verify without printing values:
  ```bash
  grep -E '^(TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID|HERMES_TELEGRAM_CHAT_ID)=' ~/.hermes/.env | sed 's/=.*/=***/'
  python3 scripts/check_telegram_connection.py
  ```
- If Hermes `send_message(target="telegram")` works, capture the returned home `chat_id` as `HERMES_TELEGRAM_CHAT_ID` only if the user approves or explicitly asks to wire project scripts to Hermes Telegram.

## News collector pattern

- Start with credential-free RSS sources in `config/news_sources.json`.
- Implement `scripts/collect_news_rss.py` as a real-data collector; never invent news.
- `scripts/news_briefing_growth_analysis.py` should call the collector and return standard workflow JSON.
- Missing OpenDART key can be an alert if RSS news still works; do not block the entire morning briefing solely because OpenDART is absent.

## Candidate compression -> opening strategy loop

- `candidate_compression_layer.py` reads real Supabase `trading_signals` + `kospi_top50` data and returns TOP 5–10 candidates.
- `run_opening_strategy_candidate_loop.py` should consume those candidates and run `run_opening_strategy_research.py` per stock for OR10/OR30.
- Do not fall back to a hard-coded stock if the compressed candidate list is empty. Return `opening_candidate_list_empty`.
- Keep `order_execution_enabled=false` and retain blocking guards such as `pattern_model_not_ready_for_auto_order` and `ka10005_timeframe_needs_market_hours_validation` until market-hours validation and 90-day intraday backtests pass.

## Leader AI approval workflow

- Keep Leader AI approval separate from Research AI scoring.
- n8n should handle approval gates and notifications; Python should compute candidates, scores, risk fields, and JSON outputs.
- Initial n8n template should be approval-only; do not connect live Kiwoom order API until the user explicitly approves live/mocked execution scope.
