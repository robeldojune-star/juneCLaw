# Signal Generation Debug Notes

Observations from session:
- The Fujimoto 1-2-6 filter (evaluate_fujimoto_126) requires a minimum score of 60, which is composed of:
    - RSI recovery: up to 15 points
    - MACD confirmation: up to 20 points
    - Ichimoku confirmation: up to 30 points
    - Market regime: up to 10 points
    - Risk control: up to 15 points
- In practice, during the tested period (2026-05-27 to 2026-06-01), many days showed scores of 0.0 with signals WATCH or BLOCKED, indicating that at least one component failed to contribute.
- Specifically, the Ichigoku component often returned insufficient data (requires 52 periods for span_b) leading to zero contribution.
- MACD and RSI did produce some signals (e.g., HIGH_CONFIDENCE_CANDIDATE for SK Hynix and Hyundai AutoEver on certain days) but the overall score remained below 60 due to missing Ichimoku or market/risk points.

Quick check:
- Run `check_signal.py` to see raw scores and component breakdown for a given stock and date range.
- To increase signal frequency, consider lowering the `min_score` parameter in the backtest or temporarily disabling certain components (e.g., set Ichimoku weight to 0) for exploratory analysis.

Next steps:
1. Verify intraday data completeness (especially for Ichimoku calculations requiring 52+ bars).
2. Experiment with component weights or min_score to understand contribution of each.
3. If the goal is to increase trade frequency for parameter optimization, start with an RSI-only signal (e.g., RSI < 30 for entry, RSI > 70 for exit) and then layer on additional filters.