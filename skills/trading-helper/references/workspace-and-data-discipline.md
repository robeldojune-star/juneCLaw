# Workspace and Data Discipline

Session learning: the user explicitly values real-data execution and was frustrated by previous fake/sample data usage. Treat this as a workflow rule for trading-system work.

## Registered WebUI workspaces

- `/home/june/trading` — current active workspace for new edits and verification.
- `/home/june/trading_workspace` — older/reference workspace containing useful material but also many buggy artifacts. Consult deliberately; do not blindly copy code from it.

## Data discipline

1. Do not fabricate market data, Kiwoom responses, scores, or backtest rows.
2. If data is missing, say so and fix the retrieval path first:
   - verify credentials/environment mode,
   - reuse known-good Kiwoom API call patterns,
   - inspect actual DB/Supabase rows,
   - repair parameter names, URLs, response-key mapping, or schema mismatch.
3. For signal-generation/backtest work, report score breakdowns and signal blockers rather than only final BUY/SELL/HOLD counts.
4. If trade frequency is implausibly low (for example ~12 trades across 130 days), investigate thresholds, max possible score, SELL path, HOLD handling, and position gating before accepting the result.

## Memory policy for this project

Durable memory is small. Put reusable implementation detail here in the skill/references, and keep memory as a short pointer to this skill plus only stable environment facts.