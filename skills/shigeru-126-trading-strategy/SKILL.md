---
name: shigeru-126-trading-strategy
description: Use when researching, validating, or applying the user's Shigeru/Fujimoto 1-2-6 trading strategy preference in /home/june/trading. Guides real ka10080 minute-data backtests, visual chart validation, OR10/OR30 comparison, and safe use as an entry-delay/confirmation filter rather than an automatic order trigger.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, kiwoom, fujimoto, shigeru, backtest, day-trading, risk]
    related_skills: [trading-helper, kiwoom-api]
---

# Shigeru / Fujimoto 1-2-6 Trading Strategy

## Overview

This skill captures the user's preferred Shigeru/Fujimoto-style 1-2-6 strategy workflow for the `/home/june/trading` project.

The user has explicitly said the Shigeru strategy appears to match their trading experience. Treat it as an important strategy candidate, but do **not** turn it into paper/real orders without real-data validation, visual 1-minute chart review, and explicit user approval.

Current validated interpretation:

- The strategy is most useful as an **entry-delay / confirmation filter** for existing BUY or OR10/OR30 candidates.
- It should not yet be treated as an independent automatic buy strategy.
- It should not yet be treated as a strong blocking filter, because the first post-backfill signal test passed all 23 BUY candidates through STAGE3.
- It may help counter the user's stated behavioral problems: fear-driven missed entries, greed-driven missed exits, and difficulty monitoring many charts at once.

## When to Use

Use this skill when the user asks about:

- 시게루 전략, 후지모토 전략, 1-2-6 분할매매, RSI/MACD/일목 confirmation
- Turning a trading video/report into a concrete strategy
- Comparing Shigeru/Fujimoto against OR10/OR30 or `opening_multi_factor_v1`
- Backtesting BUY signals on next-day `ka10080` 1-minute bars
- Creating 1-minute charts with entry/exit markers for visual validation
- Deciding whether the strategy should be a 보조 필터, 진입 지연 필터, or 독립 전략
- Explaining why paper/real orders remain blocked despite positive sample performance

Do **not** use this skill for generic Kiwoom account queries, OpenDART-only financial analysis, or unrelated long-term investing unless the user connects it to Shigeru/Fujimoto strategy validation.

## Safety Boundary

Always keep this strategy in research/shadow mode unless the user explicitly approves a next-stage rollout.

Hard rules:

1. Do not modify `opening_multi_factor_v1` directly without a separate review step.
2. Do not write to `orders` or `positions`.
3. Do not call Kiwoom order APIs.
4. Do not enable paper/real orders from this strategy.
5. Keep output fields explicit:
   - `paper_order_allowed=false`
   - `real_order_allowed=false`
   - `order_execution_enabled=false`
   - `paper_order_blocked`
   - `real_order_blocked`
6. Use only real market data. No fake/sample OHLCV for project conclusions.

Required minute-bar source:

```text
intraday_prices.source = 'kiwoom_ka10080_minute'
intraday_prices.time_frame = '1min'
```

## Data Source Clarification: Kiwoom vs Internal Indicators

In the current `/home/june/trading` implementation, Kiwoom is used for **raw market data**, not for precomputed RSI/MACD/Ichimoku signals.

| Item | Source | Current method |
|---|---|---|
| 1-minute OHLCV | Kiwoom `ka10080` via `intraday_prices` | Stored as `source='kiwoom_ka10080_minute'`, `time_frame='1min'` |
| RSI | Internal calculation | `core/fujimoto_126_filter.py::rsi_series()` from close prices |
| MACD | Internal calculation | `core/fujimoto_126_filter.py::macd_series()` using EMA from close prices |
| Ichimoku | Internal calculation | `core/fujimoto_126_filter.py::ichimoku_series()` from high/low/close bars |
| Market regime / 시황 | Currently too shallow | Only a small intraday price/volume proxy exists; broader index/news/sector regime must be added |

Therefore, when reporting this strategy, say: **"RSI/MACD/일목은 키움에서 받은 1분봉 OHLCV를 기반으로 내부 계산한다"**, not "키움에서 RSI/MACD/일목 값을 직접 받는다" unless a future Kiwoom endpoint is explicitly added and verified.

## Market Regime / 시황 Layer Requirement

The current strategy evidence is incomplete without a real 시황 layer. Before moving beyond shadow research, add a market-regime section to every report:

1. **Index regime**: KOSPI/KOSDAQ or relevant ETF/index direction, gap, intraday trend, volatility.
2. **Sector regime**: candidate stock's sector vs market, sector strength/weakness, concentration of winners/losers.
3. **News/disclosure regime**: morning news, 공시, macro risk, overnight US/FX/rates context when available.
4. **Market breadth / liquidity**: advancing/declining ratio, turnover, large-cap participation, opening volume quality.
5. **Trading decision impact**:
   - bullish regime: allow Shigeru Stage2/Stage3 as entry-delay confirmation
   - neutral/choppy regime: reduce size or require stricter Stage3 + volume confirmation
   - bearish/high-volatility regime: watchlist only or block entries unless exceptional catalyst exists

If these inputs are missing, include `market_regime_external_data_not_supplied` or keep `market_regime_not_confirmed` in `blocking_conditions`. Do not silently treat missing 시황 as neutral.

## Core Strategy Interpretation

The current implementation is based on a 1-2-6 staged confirmation model:

| Stage | Meaning | Typical Technical Confirmation |
|---|---|---|
| 1 | Initial recovery | RSI recovery from oversold or intraday recovery band |
| 2 | Momentum confirmation | MACD signal/histogram improvement |
| 6 / STAGE3 | Trend/structure confirmation | Ichimoku cloud / trend confirmation |

Practical interpretation for this user:

- Stage 1 alone is too early for automatic entry.
- Stage 2 can be used as watchlist priority improvement.
- STAGE3 can be used as delayed entry confirmation, but must still be checked against risk and market regime.
- If every candidate passes STAGE3, the filter is too permissive as a blocking filter and should be treated as an entry timing layer instead.

## Current Evidence Snapshot

Most recent important validation in `/home/june/trading`:

- Report: `reports/fujimoto_126_post_backfill_decision_2026-05-30.md`
- Backtest: `reports/fujimoto_126_backtest_signals_post_backfill.json`
- Comparison: `reports/fujimoto_or_comparison_post_backfill.json`

Validated post-backfill result:

| Metric | Result |
|---|---:|
| Signal sample | 23 BUY signals from 2026-05-28 |
| Next trading day | 2026-05-29 |
| Minute coverage after backfill | 23 / 23 |
| Entries | 23 |
| Entry rate | 100.0% |
| Average net return | +0.4969% |
| Win rate | 60.87% |
| Min / Max | -2.66% / +2.34% |
| Take profit / Stop loss / Time exit | 12 / 7 / 4 |

Comparison on same 23-code universe:

| Strategy | Trades | Win Rate | Avg Net % | Interpretation |
|---|---:|---:|---:|---|
| Shigeru/Fujimoto 1-2-6 | 23 | 60.87% | +0.4969 | Best in this small sample |
| OR10 | 16 | 43.75%* | -0.5663* | Weak |
| OR30 | 14 | 64.29%* | -0.0529* | Better than OR10 but still near/under zero |

`*` OR results were produced with the existing OR backtester aggregation pattern and should be refined with trade-level paired comparison before final deployment.

## Standard Workflow

### 1. Confirm Data Coverage

Before judging strategy performance, verify next-day minute coverage for BUY signals:

```bash
uv run --with 'psycopg[binary]' python scripts/inspect_fujimoto_missing_next_day.py \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --limit-per-date 100 \
  --json-out reports/fujimoto_126_missing_next_day_<label>.json
```

If missing rows exist, backfill `ka10080` first. Missing minute data is a data coverage issue, not a strategy failure.

### 2. Backfill Missing `ka10080` Minute Data

Use `scripts/collect_intraday_90d.py` with real Kiwoom `ka10080`:

```bash
uv run --with requests python scripts/collect_intraday_90d.py \
  --stock-codes <codes...> \
  --days 3 \
  --base-dt YYYYMMDD \
  --minute-scope 1 \
  --max-requests-per-stock 1 \
  --max-rows-per-stock 1000 \
  --delay 0.6 \
  --batch-size 500
```

Use longer windows only when needed. Respect Kiwoom rate limits and never synthesize rows.

### 3. Run Signals-Mode Backtest

Preferred operational validation is `signals` mode:

```bash
uv run --with 'psycopg[binary]' python scripts/backtest_fujimoto_126.py \
  --mode signals \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --limit-per-date 100 \
  --json-out reports/fujimoto_126_backtest_signals_<label>.json \
  --md-out reports/fujimoto_126_backtest_signals_<label>.md
```

Use `stock-days` mode only as a diagnostic for over-entry/selectivity.

### 4. Generate Visual Charts

The user expects 1-minute chart validation with entry/exit markers. Generate separate charts for:

- Take-profit cases
- Stop-loss cases
- Time-exit cases

Use the existing chart script:

```bash
uv run --with 'psycopg[binary]' --with matplotlib python scripts/create_fujimoto_126_charts.py \
  --json-in reports/fujimoto_126_backtest_signals_<label>.json \
  --out-dir reports/fujimoto_126_charts_<label> \
  --limit 6
```

Return `MEDIA:/absolute/path.png` links for important charts in WebUI.

### 5. Compare Against OR10/OR30

Compare on the same stock/date universe. Avoid comparing different populations.

Use:

- Same stock codes
- Same next trading day
- Same fee/slippage assumptions
- Similar stop/take/time-exit assumptions if possible

For the current project, comparison reports may use:

```bash
uv run --with 'psycopg[binary]' python scripts/compare_fujimoto_or_post_backfill.py
```
If writing a new comparison, make it read-only and output both JSON and Markdown.


### Enhanced Backtesting and Validation

The user prefers an enhanced backtest that incorporates multi-layer signal filters and realistic trading simulations to avoid low-probability signals and assess strategy robustness.

The skill now includes a ready-to-run script for testing re-entry after stop-loss (Option A: re-enter when price rebounds above original entry price):
- `scripts/backtest_fujimoto_custom_swing_with_reentry_quick.py` – a quick validation script that demonstrates the re-entry logic on a single stock over a short window.

### Multi-layer Signal Filters
Add the following filters to avoid entering during unfavorable conditions:
- Price > VWAP (intraday volume-weighted average price)
- Volume surge: current volume > 1.5x average volume of the last 20 bars
- Bid/ask pressure: (bid_volume - ask_volume) / (bid_volume + ask_volume) > 0.1 (indicating buying pressure)
- Volatility range: intraday ATR (14) < 3% of price (to avoid extremely volatile periods)
- Time-of-day: only enter between 09:00 and 15:00 KST (avoid first and last 30 minutes of trading)

These filters are applied as additional conditions in the signal evaluation function.

### Realistic Trading Simulation
To improve backtest realism, incorporate:
- Latency simulation: assume order execution occurs on the next 1-minute bar after signal detection (1-bar delay)
- Iceberg order simulation: assume only 10% of the intended order volume is filled at the intended price, with the remaining 90% subject to slippage
- Slippage model: use bid/ask spread at the time of signal; for buy orders, assume execution at ask price plus half the spread; for sell orders, assume execution at bid price minus half the spread
- Transaction costs: include commissions and taxes as per Korean market regulations

### Environment Separation
The user prefers to separate mock and real trading environments using explicit configuration files rather than relying on environment variable suffixes. Use:
- `config/mock.json` for mock trading settings (e.g., disabled order execution, logging only)
- `config/prod.json` for real trading settings (e.g., enabled order execution, real-time monitoring)
- The `TRADING_ENV` environment variable to select between mock and prod (values: `mock` or `prod`)
- Never store actual secrets in the config files; use `.env` for sensitive keys and only reference them in the config files if needed.

### Validation Workflow
Follow this sequence for strategy improvement:
1. Add multi-layer signal filters to the base Fujimoto 1-2-6 strategy.
2. Incorporate latency, iceberg order, and slippage simulations in the backtest.
3. Run walk-forward monthly tests: train on past 3 months, validate on the next month.
4. Perform paper trading for at least 1 month to confirm backtest results.
5. Finalize parameter set after optimization and validation.
6. Integrate the enhanced logic into `monitor_profit_exit.py` for live operation monitoring.

### Reporting Requirements
When reporting enhanced backtest results, include:
- Signal score breakdowns for each layer (base strategy, VWAP filter, volume filter, etc.)
- Blocking conditions with counts for each filter
- Visual chart validation of entry/exit points (1-minute charts with markers)
- Performance metrics: average net return, positive rate, max return, max loss, Sharpe ratio, max drawdown
- Comparison against the base strategy (without enhancements) to quantify improvement


## Decision Framework

### Use as Independent Strategy?

Current answer: **No, not yet.**

Reasons:

- Sample is still small.
- All candidates passed STAGE3 in the current validation, which means selectivity is not proven.
- Candidate-quality external data is still missing.
- Paper/real order gates remain blocked.

### Use as Blocking Auxiliary Filter?

Current answer: **Not as the primary interpretation.**

Reason: if 23/23 candidates pass, it is not filtering enough. It may become a blocking filter later if thresholds are tightened and validated.

### Use as Entry-Delay / Confirmation Filter?

Current answer: **Yes, this is the preferred research direction.**

Pattern:

1. Existing daily BUY / OR candidate identifies the opportunity.
2. Do not enter immediately at the first OR breakout.
3. Wait for Shigeru/Fujimoto Stage 2 or Stage 3 confirmation.
4. Enter only if risk gate and market regime are acceptable.
5. Keep time-exit and stop-loss logic active.

### Use as Watchlist Priority Filter?

Current answer: **Yes.**

Use score/stage to sort candidates, not to place orders automatically.

### Use as Risk Gate?

Promising but requires additional testing.

If `risk_per_trade_exceeds_limit` appears, test whether blocking those rows improves average net return and drawdown.

## Reporting Template

When reporting Shigeru/Fujimoto results, include:

```text
## 완료
- data coverage / backfill status
- signals-mode results
- chart artifacts
- OR comparison

## 핵심 성과
| metric | value |

## 차트 육안 검증
- 익절 사례
- 손절 사례
- 시간청산 사례

## OR10/OR30 비교
| strategy | trades | win_rate | avg_net | risk |

## 판단
- 독립 전략: yes/no
- 보조 차단 필터: yes/no
- 진입 지연 필터: yes/no
- watchlist priority: yes/no

## 차단 조건
- paper_order_blocked
- real_order_blocked
- candidate_quality_external_data_not_supplied
- risk_per_trade_exceeds_limit

## 다음 단계
- paired trade-level comparison
- risk-gate ablation
- more signal dates
```

## Common Pitfalls

1. **Treating missing next-day minute bars as strategy failure.** First run coverage diagnostics and collect `ka10080` rows.

2. **Using same-day minute bars for a daily BUY signal.** For daily signal replay, use the next available minute trading day after `signal_date`.

3. **Assuming positive small sample means paper trading is allowed.** Keep paper/real blocked until there are enough dates, charts, and risk-gate checks.

4. **Calling it a blocking filter when all candidates pass.** If pass rate is near 100%, it is an entry timing/priority layer, not a filter.

5. **Changing `opening_multi_factor_v1` directly.** The user prefers strategy review before modification. Use shadow comparison first.

6. **Ignoring visual validation.** The user expects 1-minute charts and will challenge entries that occur before intended signal/range formation.

7. **Using fake data.** Never use mock/random OHLCV for conclusions in this project.

## Kiwoom-vs-Internal Data Comparison

Use the read-only validator when the user asks to compare our produced data against Kiwoom-produced data:

```bash
python3 scripts/compare_our_data_vs_kiwoom.py \
  --stock-codes 005930 \
  --daily-limit 60 \
  --minute-limit 30 \
  --json-out reports/our_data_vs_kiwoom_<label>.json
```

Current interpretation:

- Direct comparison is possible for raw OHLCV:
  - Kiwoom `ka10081` fresh daily OHLCV vs `daily_prices source='kiwoom_ka10081'`
  - Kiwoom `ka10080` fresh 1-minute OHLCV vs `intraday_prices source='kiwoom_ka10080_minute'`
- Kiwoom REST docs available in this project do **not** expose verified RSI/MACD/Ichimoku indicator values. Indicator comparison is therefore recomputation-based unless a future verified endpoint or HTS export is supplied.
- `technical_indicators.daily` uses `scripts/calculate_technical_indicators.py`'s pandas formula:
  - RSI = rolling 14-period simple average gain/loss
  - MACD = `ewm(span=12/26, adjust=False)` and signal `ewm(span=9, adjust=False)`
- The Shigeru intraday filter uses `core/fujimoto_126_filter.py`, which may use different RSI/MACD warm-up/EMA conventions. Do not treat differences between daily production indicators and intraday Shigeru indicators as a data error without checking the formula.
- Supabase may store timestamps as UTC; normalize minute timestamps to KST before comparing to Kiwoom `cntr_tm`.

Smoke result on 2026-05-30 for `005930`:

- Daily OHLCV: 29/29 shared recent rows matched exactly; latest Kiwoom row `2026-05-29` had not yet been stored in daily DB sample.
- Minute OHLCV: 30/30 shared recent rows matched exactly after timezone normalization.
- Daily RSI/MACD table: 2139/2164 checked fields were within tolerance; remaining differences were early MACD/signal warm-up residuals around 2024-03.

## Extreme Low/High Signal-Marking Chart Review

When the user asks to improve charts by marking not only entry/exit but also BUY/SELL signal locations near lows/highs, the goal is **readable visual review for Shigeru/Fujimoto version-up**, not maximum marker density. See `references/readable-signal-review-charts.md` for the detailed readability rules and verification checklist.

Default to the existing `reports/backtest_trade_charts/*_entry_exit.html` Plotly style when the user says that format is good. Do not replace it with a dense chart that has every minute tick or labels on every candidate.

Use read-only review scripts and real minute data only. PNG analysis may be useful for statistics, but for user-facing review prefer an interactive HTML chart in `reports/backtest_trade_charts/` that includes candlesticks, entry/exit markers, signal markers, Korean stock names, and volume.

Example analysis command:

```bash
uv run --with 'psycopg[binary]' --with matplotlib python scripts/analyze_extreme_signal_markers.py \
  --chart-limit 10 \
  --limit-days 35 \
  --out-dir reports/backtest_trade_charts_signal_review
```

Preferred HTML review output pattern:

- `reports/backtest_trade_charts/index_signal_review.html`
- `reports/backtest_trade_charts/YYYY-MM-DD_<stock_code>_signal_review.html`
- Titles and index rows show Korean stock names, e.g. `삼성전자`, `SK하이닉스`.
- X-axis uses real datetime values, not dense `0900/0901/...` category labels.
- Volume remains visible without overwhelming the price chart.
- Full candidate counts remain in the summary, but only a few near-extreme BUY/SELL markers are displayed.

Interpretation pattern:

- BUY markers near intraday lows: `저점반등`, `RSI40회복`, `MACD전환`
- SELL markers near intraday highs: `고점거부`, `RSI70이탈`, `MACD둔화`
- Shigeru/Fujimoto stage markers: `STAGE1`, `STAGE2`, `STAGE3`
- Treat `저점반등 + RSI40회복` as early STAGE1 observation, `MACD전환` as STAGE2 confirmation, and existing Ichimoku/trend confirmation as STAGE3.
- Treat sell-side high markers as a separate exit/partial-exit layer because Shigeru is primarily a buy/entry confirmation method.
- If matplotlib emits Korean glyph warnings, set a Korean font such as `/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf` via `font_manager.addfont()` before saving PNGs.

Readability pitfalls to avoid:

1. Do not show every BUY/SELL candidate as labeled text. It hides the candles and the user will not be able to review signal quality.
2. Do not use minute strings as categorical x-values; use timestamps so Plotly controls tick density.
3. Do not make volume dominate the chart unless the user explicitly asks for a separate volume panel.
4. Do not claim a chart is improved unless it is visually closer to the user's preferred original format and easier to inspect.

## Stop-Loss Re-entry Exploration (Option A)

During this session, the user selected option A for re-entry after stop-loss: re-enter when price rebounds above the original entry price. A prototype backtest script `backtest_fujimoto_custom_swing_with_reentry_quick.py` was created and tested on SK텔레콤 (017670) over a 5-day window. Although no stop-loss events occurred in that window, prior analysis of stop-loss trades showed an average potential improvement of +3.05% net return when applying this re-entry rule.

### Implementation Notes

- The re-entry condition is evaluated only after a stop-loss exit.
- A re-entry is allowed if the current bar's close price is strictly greater than the original entry price of the position that was stopped out.
- The original entry price is stored upon stop-loss and compared against subsequent bars until a new position is entered.
- All other strategy layers (signal generation, take-profit, max holding, etc.) remain unchanged.

### Suggested Next Steps

1. Extend the backtest window to 3+ months and expand to the KOSPI Top 50 to measure the frequency of stop-loss events and the efficacy of the re-entry rule.
2. Compare option A against alternative re-entry rules:
   - Re-entry on new HIGH_CONFIDENCE_CANDIDATE signal
   - Trailing stop-loss (e.g., trail 50% of profit)
   - Fixed cooldown period (e.g., wait 2 days after stop-loss)
3. Incorporate the re-entry logic into the enhanced backtest framework that includes multi-layer filters (VWAP, volume surge, bid/ask pressure) and realistic trading simulation (latency, iceberg order, slippage).
4. Evaluate whether the re-entry rule improves the Sharpe ratio and reduces max drawdown without significantly increasing trade frequency.


## Verification Checklist

- [ ] Used `/home/june/trading` as workspace
- [ ] Used real `kiwoom_ka10080_minute` 1-minute data only
- [ ] Checked next-day minute coverage
- [ ] Backfilled missing symbols if needed
- [ ] Ran signals-mode backtest
- [ ] Generated representative PNG charts
- [ ] For chart-review tasks, marked signal points as well as entry/exit and used Korean stock names in titles/files
- [ ] For signal-review HTML charts, preserved the user's preferred `entry_exit.html`-like readability: datetime axis, visible volume, limited near-extreme markers, hover details instead of dense labels
- [ ] Compared against OR10/OR30 on the same universe
- [ ] Reported score/exit/blocking details
- [ ] Kept `paper_order_allowed=false`
- [ ] Kept `real_order_allowed=false`
- [ ] Did not modify order paths or production strategy behavior
