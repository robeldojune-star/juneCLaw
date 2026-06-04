# Opening range backtest pitfalls and current corrected pattern

Use when modifying or reviewing `/home/june/trading` OR10/OR30 backtests.

## Pitfall: first-bar breakout is not OR10/OR30

A previous implementation used the first 1-minute bar high as the breakout line. That causes entries at 09:01~09:02 and is not the intended opening-range strategy.

Correct logic:

```text
OR10:
  build range from 09:00 through 09:10
  do not enter before the range completes
  entry may occur only after 09:10 when high > OR10 high

OR30:
  build range from 09:00 through 09:30
  do not enter before the range completes
  entry may occur only after 09:30 when high > OR30 high
```

If the user says entries look like they happen at market open, check whether the backtest accidentally uses first-bar high instead of the full range high.

## Pitfall: no sell signal vs forced close

A previous OR backtest had no sell signal. It merely used the last available close as exit, which appears on charts as a sell but is not a signal.

At minimum, daytrade OR backtests should emit explicit exit reasons:

```text
stop_loss_sell_signal
take_profit_sell_signal
time_exit_sell_signal
time_exit_or_last_close  # fallback only, not a strategy signal
```

Recommended starting parameters for conservative testing:

```text
stop_loss_pct = -1.0
take_profit_pct = +1.5
time_exit = 15:20
fee_bps_one_way = 23
slippage_bps_one_way = 10
```

## Pitfall: entry window too long

Even after true OR10/OR30 range construction, unrestricted breakouts can fire at 11:00~13:00. That is no longer a strict “opening” strategy.

Add an entry window when the user wants true early-session trades:

```text
OR10 candidate entry window: 09:10~10:00 or 09:10~09:40
OR30 candidate entry window: 09:30~10:30 or 09:30~10:00
```

## Pitfall: daytrade and swing are different strategies

A user observation showed SK hynix (`000660`) 2026-05-22 first-breakout entry around 1,950,000 had poor same-day close return but strong multi-day outcomes:

```text
2026-05-26 close return: about +5.23%
2026-05-27 close return: about +15.03% (note: partial-day 2026-05-27 data in that session)
```

Do not force such cases into a daytrade-only exit model. Split variants:

```text
opening_daytrade_or_v1: intraday stop/take-profit/time-exit
opening_swing_2d_3d_v1: 1~3 trading-day hold, wider stop, trend/trailing/target exits
```

## Data eligibility

Use only complete opening days for OR tests:

```text
source == kiwoom_ka10080_minute
time_frame == 1min
09:00~09:30 coverage complete
(stock_code, timestamp) duplicates == 0
OHLC structurally valid
partial days excluded or recollected
```
