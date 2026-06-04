---
name: rsi-cci-trading-strategy
description: Trading strategy using RSI and CCI indicators with disparity and volume filters for Kiwoom 1‑minute data.
category: trading
version: 1.0
---

# RSI‑CCI Trading Strategy

This skill encapsulates a discrete‑bar trading signal generation based on:
- 20‑period moving average of close (MA20)
- Disparity = (Close / MA20) * 100
- CCI(20) on typical price
- Volume MA20 filter
- Entry: Disparity ≤ 95 AND prior CCI ≤ -100 AND current CCI > -100 AND Volume ≥ Volume MA20
- Exit (sell): RSI crossing down from ≥70 to <70 (i.e., prior RSI ≥ 70 and current RSI < 70)

The skill provides a ready‑to‑run Python script (`rsi_cci_live.py`) that:
1. Authenticates to Kiwoom REST API using environment‑based credentials (TRADING_ENV, KIWOOM_REST_API_KEY/_*_PROD, etc.).
2. Retrieves 1‑minute OHLCV bars via `ka10080` for a given date and stock code.
3. Calculates the indicators above.
4. Emits buy and sell signals (edge‑triggered).
5. Optionally can be extended to place market orders via `kt10000`/`kt10001` and send Telegram notifications.

## Usage

Run the script from the Hermes environment:

```bash
cd /home/june/trading
TRADING_ENV=prod python3 rsi_cci_live.py \
    --code 042660 \
    --date 20260601
```

The script prints detected signals to stdout. For automated monitoring, schedule it with a Hermes cron job (e.g., `*/5 9-15 * * 1-5`).

## Customisation

- Adjust periods: change `ma20`, `cci` window, `vol_ma20` window, RSI period.
- Change disparity threshold (default 95) or RSI exit threshold (default 70).
- Add additional filters (e.g., time‑of‑day, volatility).

## References

- `references/indicator_formulas.md` – detailed derivation of Disparity, CCI, RSI.
- `templates/rsi_cci_live.py` – starter script (copy‑and‑modify).
- `scripts/rsi_cci_live.py` – main signal generation script.

## Pitfalls

- Kiwoom returns signed price strings (e.g., `+126200`, `-125800`). Always take the absolute value when comparing price levels; the sign does not affect inequality logic but can confuse visualisation.
- The `ka10080` endpoint may return data for the previous trading day if the requested date is a holiday or weekend. Filter the resulting DataFrame to the desired date using `df['time'].dt.date == target_date`.
- Ensure the virtual environment (`venv`) under `/home/june/trading_workspace` is activated or use the Hermes‑managed Python (`/home/june/.hermes/hermes-agent/venv/bin/python`) to have `pandas` and `numpy` available.
