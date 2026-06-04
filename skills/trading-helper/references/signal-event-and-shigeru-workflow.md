# Signal-event and Shigeru-style workflow lessons

Use this reference when the user discusses Fujimoto/Shigeru-style signal-driven trading, missed entries/exits, daily-to-minute signal alignment, or whether generated signals are being used effectively.

## Core intent

The user's goal is not simply auto-ordering or higher backtest return. The system should reduce human behavioral failure:

```text
Fear: signal appears but human does not enter.
Greed: exit/sell signal appears but human does not sell.
Attention limit: human cannot monitor many 1-minute charts at once.
```

So the workflow should prioritize:

```text
automatic observation < automatic recording < automatic feedback < paper ledger < real pilot
```

Do not jump from a BUY signal directly to order execution.

## Strategy structure

Treat the Shigeru/Fujimoto-style approach as a layered signal workflow:

1. **Market/sector context**: market bias, theme/sector strength, news/briefing.
2. **Daily candidate signal**: `technical_score_v1` or equivalent daily BUY/HOLD/SELL candidate generation.
3. **Candidate compression**: TOP 5~30 watchlist; do not lose blocked outcomes.
4. **Minute entry signal**: OR10/OR30, 10:00 bar, volume confirmation, pullback/rebreak.
5. **Exit/hold signal**: stop, take-profit, time-exit, trailing stop, trend break, or swing hold.
6. **Outcome analysis**: after 1m/3m/5m/1d/3d returns, including missed signals.

Separate at least two variants:

```text
shigeru_intraday_v1: same-day OR entry + stop/take-profit/time exit.
shigeru_swing_3d_v1: daily signal + minute entry + 1~3 trading-day hold/exit logic.
```

## Signal events are mandatory

Generated signals must not disappear just because later gates block orders. Record event-level outcomes even when no order is placed.

Recommended `event_type` taxonomy:

```text
DAILY_ENTRY_CANDIDATE
INTRADAY_ENTRY_SIGNAL
BLOCKED_ENTRY_SIGNAL
MISSED_ENTRY
EXIT_SIGNAL
MISSED_EXIT
PAPER_ORDER_CANDIDATE
```

Minimum event payload:

```json
{
  "event_type": "DAILY_ENTRY_CANDIDATE",
  "stock_code": "005930",
  "strategy": "technical_score_v1",
  "signal_time": "2026-05-28T15:30:00+09:00",
  "signal_price": 299500,
  "score": 82,
  "score_details": {},
  "blocking_conditions": [],
  "system_recommendation": "WATCH_OR_ENTRY_CANDIDATE",
  "human_action": "NONE",
  "outcome": {
    "after_1m_return_pct": null,
    "after_3m_return_pct": null,
    "after_5m_return_pct": null,
    "after_1d_return_pct": null,
    "after_3d_return_pct": null
  }
}
```

## Diagnostic lesson from this session

Observed signal flow:

```text
technical_score_v1 daily signals: produced normally (BUY/HOLD/SELL).
candidate_compression_layer: compressed daily BUYs into TOP candidates.
opening candidate loop: converted most candidates to HOLD/blocked.
paper orders: none, because buy_candidate_count=0.
orders/positions: empty.
missed_entry/missed_exit: not recorded.
```

Diagnosis:

```text
Signal generation was not the main problem; signal utilization was.
```

When daily BUYs are blocked by intraday/fundamental/Fujimoto gates, record `BLOCKED_ENTRY_SIGNAL` and later outcome. This answers whether the block protected the user or caused a missed opportunity.

## Daily-to-minute scenario analysis pattern

The user may ask about a daily signal on one date, a minute entry at a specific time, and whether sell signals appeared later. This is valid and should be analyzed with real data:

```text
Daily BUY signal date = D
Minute entry date/time = D at HH:MM
Entry price = ka10080 1min close at HH:MM
Check same-day 15:00/15:20/15:30 returns
Check D+1/D+2/D+3 returns
Detect first exit signal: stop_loss, take_profit, time_exit, trend_break
```

Example from session: Samsung `005930`, hypothetical daily signal on 2026-05-22, 10:00 minute entry at 292,750. Outcome using real data:

```text
2026-05-22 15:00 return ≈ +0.0854%; no -2% stop or +5% take-profit.
2026-05-26 15:30 return ≈ +2.1349%.
2026-05-27 first available minute data showed +5% take-profit condition.
```

Caveat: label hypothetical daily signals separately from stored `trading_signals`. If a date has partial minute data, report it explicitly.

## Entry/exit pitfalls

- Do not call first-bar breakout an OR10/OR30 strategy. OR10 must build range through 09:10 and only enter after; OR30 through 09:30 and only enter after.
- If the user wants "장초반 진입", add an `entry_end` window (e.g. OR10 09:10~10:00, OR30 09:30~10:30). Otherwise late entries at 11:00~13:00 can occur.
- Do not rely on forced last-close exits and call them sell signals. Emit explicit exit reasons:
  - `stop_loss_sell_signal`
  - `take_profit_sell_signal`
  - `time_exit_sell_signal`
  - `trailing_stop_signal`
  - `trend_break_signal`
- Same-day stops/take-profits can destroy swing opportunities. Evaluate intraday and 1~3 day swing variants separately.

## Reporting standard

When discussing strategy state, report these separately:

```text
signals_generated
candidates_compressed
intraday_entry_signals
blocked_entry_signals
paper_order_candidates
open_positions
exit_signals
missed_entry/missed_exit outcomes
```

Avoid saying "no signal" when daily signals exist but were blocked downstream. Say exactly where the flow stopped.