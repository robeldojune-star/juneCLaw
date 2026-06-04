# Human behavior guard + signal event logging

Use this reference when the user frames the trading system as a way to overcome human fear/greed and multi-symbol attention limits, not just as a raw backtest engine.

## Core purpose

The user's goal is to reduce these failure modes:

```text
- Fear: a valid entry signal appears but the human cannot enter.
- Greed/hope: an exit signal appears but the human cannot sell.
- Attention limit: multiple 1-minute charts/signals cannot be watched at once.
```

Therefore prioritize this rollout order:

```text
automated observation -> automated recording -> feedback reports -> paper ledger -> real pilot
```

Do not jump directly from backtest to automatic real orders.

## Required signal event vocabulary

Record signals whether or not an order is executed.

```text
ENTRY_SIGNAL     A mechanical entry condition fired.
EXIT_SIGNAL      A mechanical sell/exit condition fired.
MISSED_ENTRY     ENTRY_SIGNAL occurred but the human/system did not enter.
MISSED_EXIT      EXIT_SIGNAL occurred but the human/system did not exit.
BLOCKED_SIGNAL   A candidate signal was blocked by data/risk/readiness conditions.
```

Recommended minimal fields:

```text
event_id
event_type
stock_code
strategy
signal_time
signal_price
trigger
score
score_details
blocking_conditions
system_recommendation
human_action
outcome JSON: after_1m/3m/5m/1d/3d returns, max_seen_return, adverse excursion
created_at
```

## Why this matters

For every signal, the system should be able to answer later:

```text
- Was there really a signal?
- At what exact 1-minute bar and price?
- Why did the strategy recommend entry/exit?
- Did the human/system act?
- If not, what happened 1m/3m/5m/1d/3d later?
- Did fear or greed help or hurt?
```

## Example: missed entry

```json
{
  "event_type": "MISSED_ENTRY",
  "stock_code": "000660",
  "strategy": "opening_swing_candidate_v1",
  "signal_time": "2026-05-22T09:01:00+09:00",
  "signal_price": 1950000,
  "human_action": "NOT_ENTERED",
  "reason": "human_fear_or_manual_delay",
  "outcome": {
    "same_day_close_return_pct": -0.4615,
    "next_trading_day_close_return_pct": 5.2308,
    "third_trading_day_close_return_pct": 15.0256,
    "max_seen_return_pct": 19.641
  }
}
```

## Implementation guidance

Prefer a dedicated `signal_events` table over overloading `trading_signals`:

```sql
signal_events (
  event_id text primary key,
  event_type text not null,
  stock_code text not null,
  strategy text not null,
  signal_time timestamptz not null,
  signal_price numeric,
  trigger text,
  score numeric,
  score_details jsonb,
  blocking_conditions jsonb,
  system_recommendation text,
  human_action text,
  outcome jsonb,
  created_at timestamptz default now()
)
```

Keep `order_execution_enabled=false` until readiness + paper validation pass. Event logging is safe because it is observational.
