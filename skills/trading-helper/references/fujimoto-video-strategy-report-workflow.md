# Fujimoto/YouTube Strategy Report Workflow

Use this reference when the user provides a trading-strategy YouTube video and asks for a strategy report or implementation plan.

## Durable workflow

1. **Load the transcript first**
   - Use the `youtube-content` skill/helper when a YouTube URL is provided.
   - Prefer timestamped transcript output.
   - If the default transcript query fails with "No transcript found", retry with explicit language fallbacks such as `--language ko,en,ja` before giving up.
   - Do not summarize from the video title alone.

2. **Separate video claims from system strategy**
   - Extract the video's raw claims/techniques.
   - Translate them into explicit, testable trading rules.
   - Mark unverified claims as candidates, not proven strategy.

3. **Respect trading project safety gates**
   - Do not change thresholds, weights, order behavior, or execution code while writing the report.
   - Keep `paper_order_allowed=false` and `real_order_allowed=false` unless separate backtest/paper gates and user approval exist.
   - For Korean equities, treat short-selling examples as conceptual unless the user explicitly asks to model short constraints.

4. **Recommended report structure**
   - Executive Summary
   - Source/video summary
   - Strategy hypothesis and system-fit assessment
   - Entry rules
   - Exit rules
   - Risk management and position sizing
   - Score breakdown schema
   - Integration with `opening_multi_factor_v1` / OR10/OR30 if applicable
   - Data requirements (`ka10080` for historical 1min backtest, `ka10006 snapshot_1m` for live monitoring)
   - Backtest plan and comparison groups
   - Visual 1-minute chart validation requirements
   - Blocking conditions and order safety gates
   - Implementation phases and decision points

5. **Fujimoto 1-2-6 default mapping**
   - `strategy_id`: `fujimoto_126_trend_confirmation_v1`
   - Preferred initial role: auxiliary confirmation filter for `opening_multi_factor_v1`, not standalone auto-order strategy.
   - Long Stage 1: RSI recovery/probe signal, candidate 1/9 size.
   - Long Stage 2: MACD confirmation, additional 2/9 size.
   - Long Stage 3: Ichimoku confirmation/cloud breakout plus retest/support, additional 6/9 size.
   - Exit Stage 1: MACD dead cross, partial trim.
   - Exit Stage 2: RSI 50 loss, additional trim.
   - Exit Stage 3: cloud/support breakdown, remaining exit.
   - Convert "no stop loss" marketing language into explicit hard risk gates; never run without loss limits.

6. **Deliverables**
   - Markdown source under `reports/` or `docs/strategies/`.
   - DOCX copy under `reports/documents/` when the user asks for a report/document.
   - Use `python-docx` via an isolated runtime (for example `uv run --with python-docx ...`) if project/system Python lacks the package; this is a creation pattern, not a permanent environment assumption.

## Report quality checklist

- Korean language unless user requests otherwise.
- Tables for thresholds, score details, data sources, and safety gates.
- Explicit `blocking_conditions` list.
- Explicit statement that no code/threshold/order changes were made if the task was report-only.
- No sample/mock market data used to imply validation.
- Backtest claims only after real `ka10080`/Supabase data verification.
