# RSI‑CCI Profit‑Target Strategy

This skill provides a script (`rsi_cci_profit_target.py`) that implements an intraday trading strategy:

- **Entry**: disparity20 ≤ 100, CCI crosses -100 upward, volume ≥ 20‑period MA of volume.
- **Exit**: Fixed profit target (default +1.5%) reached intraday.

The script can be used for backtesting over a look‑back window (default last 5 trading days) or as a basis for live signal generation.

## Files

- `scripts/rsi_cci_profit_target.py` – main executable script.
- `references/README_rsi_cci_profit_target.md` – this file.

## Usage

From the trading workspace (`/home/june/trading`):

```bash
python3 scripts/rsi_cci_profit_target.py \
    --stock 042660 \
    --end-date 20260601 \
    --lookback 5 \
    --profit-target 1.5 \
    [--show-plots]
```

See the skill’s main SKILL.md for more details on automation with Hermes cron, real‑time alerts, and order execution.