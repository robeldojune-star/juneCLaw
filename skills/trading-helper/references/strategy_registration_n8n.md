# Strategy registration + n8n operating workflow

Session learning for the trading project class of tasks: registering a research strategy into docs/code/n8n without prematurely turning it into live trading.

## Recommended sequence

When user asks to register a new trading strategy from research material:

1. Extract/source research material into Git-trackable markdown references; keep original Word/PDF/binary docs ignored.
2. Create/update `docs/strategies/investment_strategy_registry_v*.md` with:
   - strategy id
   - source documents
   - pillars/factors
   - candidate scoring weights
   - data requirements
   - implementation blockers
   - explicit non-advice warning
3. Create/update machine-readable `docs/strategies/strategy_registry.json`.
4. Keep uncertain ideas as `*_candidate` / `research_required`; do not hard-code them as trade rules.
5. Build pure scoring modules under `core/` and bridge scripts under `scripts/` that print JSON for n8n.
6. Add n8n workflow docs/templates under `workflows/n8n/`, but keep n8n as orchestration only.
7. Validate JSON, py_compile, run smoke scripts, scan staged diff for secrets, then commit.

## Strategy scoring module pattern

Keep strategy logic deterministic and side-effect free:

```text
core/opening_strategy.py       # pure scoring
core/market_data_service.py    # Kiwoom data access
scripts/run_*_research.py      # JSON bridge for Research AI/n8n
scripts/backtest_*.py          # real-data-only backtest or explicit blockers
```

Output JSON should include:

```json
{
  "ok": true,
  "workflow": "run_opening_strategy_research",
  "strategy_id": "opening_multi_factor_v1",
  "stock_code": "005930",
  "signal_type": "HOLD",
  "score": 15.0,
  "score_details": {},
  "blocking_conditions": [],
  "data_quality": {}
}
```

## Real-data-first blocker pattern

If data is not ready, do not fabricate sample rows. Return explicit blockers:

```text
need_90_trading_days_intraday_prices
need_market_hours_validation_for_ka10005_timeframe
need_transaction_cost_and_slippage_assumptions
pattern_model_not_ready
```

This matches the user's preference for real Kiwoom/OpenDART/Supabase data only.

## n8n role boundary

n8n should:

```text
- schedule
- execute scripts
- parse JSON
- branch on ok/score/blocking_conditions
- notify Telegram/Webhook/Hermes
```

n8n should not:

```text
- contain strategy math
- directly compute order size
- hide missing data
- execute orders from a research workflow
```

Initial workflow should be alert-only. Order candidate creation belongs in a separate Leader AI workflow after backtest/mock-trading validation.

## Research uncertainties

For user-interest strategies like 후지모토 시게루:

- Create a research note under `docs/strategies/`.
- Record public-source findings as candidates, not confirmed rules.
- Prefer integration as an auxiliary filter until original/source material is verified.
- Example candidate elements: fundamentals filter, RSI 30/70 timing, 1m/5m chart timing, volume/trading-value confirmation, staged 1:2:6 entry.
