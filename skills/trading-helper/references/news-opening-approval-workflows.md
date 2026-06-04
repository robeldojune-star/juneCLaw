# News → Candidate Compression → Opening Loop → Leader Approval Workflow

Use this reference when extending the user's multi-AI/n8n trading workflow beyond the base daily runner.

## Trigger

Use when the user asks to wire daily trading workflows, RSS/news briefing, 09:10/09:30 opening strategy loops, Telegram alerts, or Leader AI approval/order gates.

## Durable pattern

1. Keep n8n as scheduler/orchestrator only.
2. Put all calculations and API parsing in versioned Python scripts under the active trading repo.
3. Every script prints JSON with `ok`, `workflow`, `stage`, `status`, `summary`, `alerts`, `blocking_conditions`, and `next_actions`.
4. If credentials or data are missing, report explicit `blocking_conditions`; do not fabricate market/news/order data.
5. Order execution stays separated from Research/Monitoring workflows until Leader/human approval is wired.

## RSS/news collector pattern

- Keep source list in a JSON config such as `config/news_sources.json`.
- Start with credential-free RSS feeds for initial wiring; add paid/Naver/other APIs only after key and terms are confirmed.
- A collector script should:
  - fetch each RSS source with a clear user-agent,
  - parse title/link/pubDate/description,
  - deduplicate by `(title, link)`,
  - return `source_errors` separately from global blockers,
  - only block if no usable items are collected.
- Morning briefing stage can treat missing OpenDART as an alert when RSS news is available; it should not block the whole briefing solely because DART is not configured.

## Candidate compression → opening strategy loop

- Pre-market candidate compression should read real `trading_signals` and `kospi_top50` rows from Supabase/DB.
- Compress to TOP 5~10 before 09:00 to avoid losing entry timing.
- Convert the compressed candidates into a `today_watchlist` bridge stage before intraday monitoring; include watch priority, OR10/OR30 scenarios, score details, and explicit `paper_order_allowed=false` / `real_order_allowed=false` safety flags.
- The intraday timing alert stage (`scripts/run_intraday_timing_alerts.py`) should evaluate `today_watchlist` against `intraday_prices` rows with `source=kiwoom_ka10006_snapshot` and `time_frame=snapshot_1m` only, emitting alert-only OR10/OR30 timing events.
- The 09:10 and 09:30 opening stages should evaluate the compressed candidate list or `today_watchlist`, not a hardcoded single stock, once wiring is mature.
- Keep `order_execution_enabled=false`, `paper_order_allowed=false`, and `real_order_allowed=false` in intraday/opening outputs until Leader approval + backtest/paper gates pass.
- Keep these blockers until validated:
  - `pattern_model_not_ready_for_auto_order`
  - `ka10005_timeframe_needs_market_hours_validation`
  - missing 90-day intraday backtest

## Leader AI approval workflow

Create a separate approval workflow rather than adding orders to Research AI scripts.

Recommended flow:

```text
opening candidate loop
→ blocking_conditions empty?
→ Monitoring AI account/risk check
→ Telegram/manual approval request
→ approved_order_execution workflow only after approval
→ orders/trading_signals update
```

Initial Leader approval criteria for the user's 1,000,000 KRW day-trading budget:

| Check | Starting value |
|---|---:|
| opening score | >= 70 |
| signal_type | BUY |
| blockers | none |
| max symbols | 3 |
| per-symbol budget | 200k~300k KRW |
| daily total budget | <= 1,000,000 KRW |
| stop reference | -0.7%~-0.9% |
| take-profit reference | +1.0%, +2.0% |

## n8n/Telegram connection

- n8n UI import can be manual, or API-based if `N8N_URL` and `N8N_API_KEY` are configured.
- Telegram can be wired in n8n credentials, or checked locally with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- Do not store these secrets in Git or chat.
- Telegram messages should include only stage/status/summary/alerts/blocking_conditions/next_actions.

## Verification checklist

Run the equivalent of:

```bash
python3 -m json.tool config/news_sources.json
python3 -m json.tool workflows/n8n/*.json
python3 -m json.tool docs/strategies/strategy_registry.json
python3 -m py_compile core/*.py scripts/*.py
python3 scripts/collect_news_rss.py
python3 scripts/run_daily_workflow_stage.py --stage news_briefing_growth_analysis
python3 scripts/run_opening_strategy_candidate_loop.py --window 10 --limit 3
python3 scripts/run_daily_workflow_stage.py --stage opening_10m_aggressive_layer
python3 scripts/run_daily_workflow_stage.py --stage opening_30m_standard_layer
```

Expected safe state before order validation:

- RSS collector can complete with real items.
- Opening candidate loop can complete on TOP candidates.
- 09:10/09:30 daily stages remain `blocked` because the auto-order guards are still active.
- Secret scan passes before commit.
