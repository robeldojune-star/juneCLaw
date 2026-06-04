# Fujimoto Auxiliary Filter v1 Integration Notes

## Why this matters
When extending `opening_multi_factor_v1` with user-requested Fujimoto-style constraints, we needed a **class-level, non-invasive integration**:
- Keep existing `total_score` semantics for continuity.
- Add a separate auxiliary gate for BUY qualification.
- Emit explicit machine-readable blocks when required data is unavailable.

This prevents silent overfitting and keeps operations aligned with current readiness gates.

---

## Implemented pattern (session-proven)

### 1) Input schema extension (safe defaults)
`core/opening_strategy.py` `OpeningStrategyInput` was extended with nullable fields:
- `turnover: float | None`
- `operating_income_positive: bool | None`
- `earnings_trend_ok: bool | None`
- `stage_entry_ready: bool | None`

Rule: default to `None` until data is truly wired, and emit blocking conditions instead of fabricating values.

### 2) New auxiliary scorer
Add `fujimoto_aux_filter_score(inp)` returning:
- `(score: 0..15, details: dict, blocks: list[str])`

Subscores:
- Financial quality (max 5)
- RSI regime (max 4)
- Liquidity/turnover (max 3)
- Staged-entry readiness (max 3)

### 3) BUY gate tightened without disturbing core score
In `score_opening_multi_factor`:
- Keep `total = v + f + p + r` unchanged.
- Add aux gate condition for BUY:
  - `total >= 70` **and** `fujimoto_aux_score >= 8`
- Keep HOLD/WATCH behavior explicit.

### 4) score_details schema extension
Append:
- `score_details.fujimoto_aux_filter`
- `score_details.thresholds.fujimoto_aux_min`

This is consumed by loop-level filters and reporting.

### 5) Candidate loop defensive re-check
In `run_opening_strategy_candidate_loop.py`, BUY candidate selection should additionally verify:
- `score_details.fujimoto_aux_filter.score >= score_details.thresholds.fujimoto_aux_min`

Do not rely only on `signal_type == "BUY"`.

---

## Blocking conditions taxonomy (recommended)

Use dedicated, diagnosable names:
- `fujimoto_financial_data_missing`
- `fujimoto_financial_filter_failed`
- `fujimoto_rsi_missing`
- `fujimoto_rsi_overheated`
- `fujimoto_volume_insufficient`
- `fujimoto_turnover_insufficient`
- `fujimoto_stage_entry_not_ready`

Keep common global gates unchanged (e.g. `pattern_model_not_ready`).

---

## Pitfalls discovered

1. **Type safety with optional volume values**
If `volumes = [b.volume ...]`, static typing may infer `float | None` and break `mean(...)` typing.
Use normalized numeric extraction first:
```python
volumes = [v for b in inp.bars if (v := _num(b.volume)) is not None]
```

2. **Aux filter can collapse BUY to zero when data is not wired**
This is expected in conservative mode. Treat as intended shadow/guard behavior, not strategy failure.

3. **Keep alert-only/paper-only policy until readiness gate passes**
Even with new auxiliary logic, maintain no-auto-order policy while:
- rows/trades backtest gates are below thresholds
- pattern model is still placeholder/not validated

---

## Minimal verification routine

1. Syntax check:
```bash
python3 -m py_compile core/opening_strategy.py scripts/run_opening_strategy_research.py scripts/run_opening_strategy_candidate_loop.py
```

2. Single-stock probe:
```bash
python3 scripts/run_opening_strategy_research.py --stock-code 005930 --limit-bars 10
```
Confirm presence of:
- `score_details.fujimoto_aux_filter`
- `thresholds.fujimoto_aux_min`
- explicit `fujimoto_*` blocking conditions when inputs are missing.

3. Loop probe:
```bash
python3 scripts/run_opening_strategy_candidate_loop.py --window 10 --limit 3
```
Confirm BUY candidates are filtered by aux threshold and blocks.
