# OR10/OR30 backtest visual validation and implementation pitfalls

Use this reference when implementing or reviewing opening-range backtests for `/home/june/trading`.

## User expectation

The user expects a backtest to be visually inspectable on 1-minute charts by specific stock/date. For each trade, show:

```text
- 1-minute candles
- range-building window
- signal line / range high
- actual signal/entry marker
- exit marker
- net return after costs
```

If a chart does not render in WebUI as HTML/Plotly, generate static PNG charts and return `MEDIA:/absolute/path.png` links.

## Critical strategy pitfall

Do not confuse these two strategies:

```text
WRONG: first 1-minute bar high breakout
RIGHT: OR10/OR30 opening range breakout after the range is complete
```

The wrong implementation enters almost at market open (09:01~09:02) and falsely looks like a 장초반 strategy. The user caught this; treat it as a serious implementation bug.

## Correct OR10 / OR30 definitions

### OR10

```text
range window: 09:00~09:10
entry allowed only after range is complete: >09:10, usually 09:11 onward
range_high = max(high) over 09:00~09:10
signal/entry = first bar after 09:10 whose high > range_high
```

### OR30

```text
range window: 09:00~09:30
entry allowed only after range is complete: >09:30, usually 09:31 onward
range_high = max(high) over 09:00~09:30
signal/entry = first bar after 09:30 whose high > range_high
```

For a true “장초반 only” strategy, also add an entry end time:

```text
OR10 candidate: 09:10~10:00 or stricter 09:10~09:40
OR30 candidate: 09:30~10:30 or stricter 09:30~10:00
```

Without an entry end time, signals can occur at 11:00~13:00 and are no longer a strict opening strategy.

## Data eligibility before backtest

Use `ka10080` historical 1-minute bars:

```text
source = kiwoom_ka10080_minute
time_frame = 1min
```

For OR10/OR30, use only eligible stock×date rows:

```text
09:00~09:30 complete
no duplicate opening minutes
OHLC structurally valid
partial days excluded or recollected
```

## Cost assumptions

Backtest should expose cost parameters and report them:

```text
--fee-bps 23
--slippage-bps 10
```

For paper ledger modeling, include optional impact:

```text
fee_bps_one_way
slippage_bps_one_way
impact_bps_one_way
assumed_fill_price
estimated_fee
estimated_cash_effect
```

## Verification checklist

After modifying the backtest:

1. Run syntax check:

```bash
python3 -m py_compile scripts/backtest_opening_strategy.py scripts/create_backtest_trade_static_charts.py
```

2. Run backtest with eligible-day filter and costs:

```bash
python3 scripts/backtest_opening_strategy.py \
  --stock-codes 005930 000660 035420 005380 068270 \
  --days 130 \
  --time-frame 1min \
  --source kiwoom_ka10080_minute \
  --eligible-opening-only \
  --fee-bps 23 \
  --slippage-bps 10
```

3. Confirm entry times:

```text
OR10 entry_time_min must be > 09:10
OR30 entry_time_min must be > 09:30
```

4. Generate PNG charts, not only HTML:

```bash
python3 scripts/create_backtest_trade_static_charts.py --window 10 --limit 6 --out-dir reports/backtest_trade_charts_static_or10
python3 scripts/create_backtest_trade_static_charts.py --window 30 --limit 6 --out-dir reports/backtest_trade_charts_static_or30
```

5. Return chart links in the response:

```text
MEDIA:/home/june/trading/reports/backtest_trade_charts_static_or10/<file>.png
MEDIA:/home/june/trading/reports/backtest_trade_charts_static_or30/<file>.png
```

## Interpretation rule

Rows/trades passing is not enough. If average return remains negative after fees/slippage, do not move to paper/real. Treat it as strategy diagnosis and visually inspect entries/exits first.
