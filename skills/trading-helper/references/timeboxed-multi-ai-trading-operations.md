# Time-boxed Multi-AI Trading Operations

Use this reference when designing daily n8n/Hermes/Python workflows for the trading project. It captures the class-level operating pattern learned from the user's 1-week, ~1M KRW live-budget experience.

## Core lesson

Separate **pre-market analysis** from **real-time execution**. If news/research/snapshot analysis is still running after the market opens, the system can miss the actual buy timing.

Recommended layers:

| Layer | Time | Purpose | Heavy analysis? |
|---|---|---|---|
| Pre-analysis | 07:00-08:30 | News, disclosures, OpenDART, prior OHLCV, indicators, candidate selection | Yes |
| Execution prep | 08:30-09:00 | API smoke, kt00004 account/risk check, compress candidates to TOP 5-10 | Limited |
| Real-time execution | 09:00-10:00 | Snapshot/minute bars, OR10/OR30, volume spike, blocking conditions | No |
| Monitoring | 10:00-15:00 | Positions, PnL, failed entries, fills, risk | No |
| Feedback | 15:00-16:30 | Selloff, OHLCV collection, daily PnL/failure report | Medium |
| Strategy review | 20:00+ as needed | Deep review and strategy changes | High-grade model |

## Suggested schedule skeleton

| Time | Workflow | Owner | Model grade | Notes |
|---|---|---|---|---|
| 06:50 | system_health_check | Monitoring AI / n8n | low/none | Server/env/API readiness |
| 07:00 | news_briefing_growth_analysis | Research AI | medium-high | News/disclosures/growth themes -> Telegram |
| 07:30 | stock_morning_signals | Research AI | medium | Prior-day data signal generation |
| 08:00 | stock_trading_daily_workflow | n8n + Python | low-medium | ETL check -> indicators -> signals -> order-check report |
| 08:30 | premarket_account_risk_check | Monitoring AI | low | kt00004 cash/account/positions/risk events |
| 08:45 | candidate_compression_layer | Leader AI | medium | Reduce to real-time watchlist TOP 5-10 |
| 09:00 | morning_investment_layer | Leader AI | low | Stabilize snapshots; avoid immediate blind buys |
| 09:10 | opening_10m_aggressive_layer | Research/Leader | low | OR10 aggressive alert/mock only at first |
| 09:30 | opening_30m_standard_layer | Research/Leader | low | OR30 standard default candidate layer |
| 10:00 | post_opening_monitoring | Monitoring AI | low | Record missed/failed/blocked entry reasons |
| 11:30 | midday_position_review | Monitoring AI | low | Position PnL/risk check |
| 14:30 | pre_close_risk_review | Monitoring AI | low | Stop/take-profit/close candidate review |
| 15:00 | evening_selloff_layer | Leader/Monitoring | low | Selloff/risk reduction |
| 15:20 | aftermarket_multi_timeframe_collection | Python | none | Intraday/daily/multi-timeframe collection |
| 15:40 | stock_nightly_collection | Python/n8n | none | Confirmed OHLCV collection |
| 16:10 | daily_pnl_feedback_report | Monitoring AI | medium | PnL, signal-vs-execution, failure causes |
| 20:00 | strategy_review_if_needed | Hermes/Research | high | Only when daily/weekly feedback warrants changes |

## Daily feedback loop

Every trading day should produce a report containing:

- realized/unrealized PnL, return %, estimated fees/slippage
- BUY/WATCH/HOLD/NO_TRADE counts
- which signals were executed and which were skipped
- blocking conditions: data missing, score below threshold, low liquidity, API/account issue, risk filter
- failure categories: late signal, false breakout, missed fill, stop loss, overheat entry, stale data
- proposed adjustments: thresholds, weights, new strategy registration, data collection fixes

Storage rule:

| Item | Where to store |
|---|---|
| Daily PnL/logs | DB/reports/session, not memory |
| Durable repeated lesson | skill or compact memory |
| Strategy change candidate | docs/strategies + strategy_registry |
| Final strategy number | machine-readable JSON + code |
| Secrets | `.env` only |

## V-factor weighting for day trading

For intraday/day-trading strategies, valuation/V-factor should not dominate entry decisions. Use it as a risk/quality filter unless the strategy is explicitly swing/long-term.

| Strategy type | Price/flow | Pattern | Valuation/V-factor | Risk |
|---|---:|---:|---:|---:|
| Day trading | 55-65% | 15-25% | 5-10% | 15-20% |
| Swing | 35-45% | 20-25% | 20-30% | 10-15% |
| Long-term | 20-30% | 10-20% | 40-50% | 10-20% |

## Model/API cost discipline

- Use high-grade models for strategy research, deep reviews, and high-impact interpretation.
- Use medium models for daily news summaries and PnL/failure explanations.
- Use low-grade models or no LLM for routine JSON checks, monitoring, ETL, and deterministic calculations.
- Keep n8n responsible for scheduling/branching/retries/alerts; keep formulas, Kiwoom parsing, score math, and order sizing in versioned Python.
- Always consider whether expected trading edge can cover API/model costs.

## n8n implementation rule

Each workflow stage should call a Python script that emits a consistent JSON envelope:

```json
{
  "ok": true,
  "workflow": "stock_morning_signals",
  "stage": "pre_market",
  "summary": "...",
  "metrics": {},
  "blocking_conditions": [],
  "next_action": "..."
}
```

n8n should parse this envelope and route to Telegram/Hermes/approval gates. Do not spread strategy formulas across n8n Function nodes.