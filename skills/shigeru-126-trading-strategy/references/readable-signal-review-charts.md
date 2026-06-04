# Readable Signal-Review Charts for Shigeru/Fujimoto Validation

Use this reference when improving `/home/june/trading/reports/backtest_trade_charts/` charts for low/high signal review.

## Durable lesson from user feedback

The user rejected a chart that technically added signal markers but made the visual review harder. For this user, a Shigeru/Fujimoto chart upgrade must preserve the familiar `*_entry_exit.html` Plotly style and improve readability, not simply add more indicators.

## Preferred chart shape

- Keep the original dark Plotly candlestick layout close to existing `*_entry_exit.html` charts.
- Show Korean stock names prominently, e.g. `삼성전자`, `SK하이닉스`, not only stock codes.
- Include entry/exit markers and signal markers.
- Include volume, but avoid a huge separate volume panel unless explicitly requested. A thin right-axis/overlay style can be easier to compare with the original chart.
- Use real `kiwoom_ka10080_minute` 1-minute bars only.
- Keep the task read-only: no order writes, no position changes.

## Marker-density rules

Do not label every candidate on the chart. That creates an unreadable wall of labels.

Recommended display policy:

1. Compute all candidates and keep full counts in the report/summary.
2. Visually display only high-quality near-extreme candidates, e.g. within 0.7% of the day's low for BUY candidates or within 0.7% of the day's high for SELL candidates.
3. Cap displayed markers per side, e.g. 6-8 max.
4. Enforce spacing between displayed markers, e.g. at least 10 minutes apart, so clusters do not overlap.
5. Prefer marker-only traces with hover details. Do not put `MACD전환`, `RSI40회복`, `저점반등` text labels on every point unless the user asks for dense annotation.

## Time-axis rules

Use real datetime x-values such as `2026-05-28T09:00:00+09:00`, not dense string labels like `0900`, `0901`, `0902`. Dense string labels make Plotly render every minute tick and the x-axis becomes unreadable.

## Signal interpretation for review

- BUY near lows: `저점반등`, `RSI40회복`, `MACD전환`
- SELL near highs: `고점거부`, `RSI70이탈`, `MACD둔화`
- Shigeru markers: `STAGE1`, `STAGE2`, `STAGE3`

For strategy-version-up work, treat this as a visual review layer before changing strategy behavior. The goal is to decide which signals are useful near low/high extremes; do not directly promote them into live/paper order logic.

## Verification checklist

After regenerating charts, verify at least one generated HTML file contains:

- Korean `stock_name`
- datetime x-axis values
- `mode:'markers'` for dense BUY/SELL signal traces
- volume trace present
- signal counts vs displayed counts in the summary/index
- `paper_order_allowed=false`, `real_order_allowed=false`, or equivalent read-only wording in outputs
