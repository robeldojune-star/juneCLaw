# README for RSI‑CCI strategy
Place this file alongside rsi_cci_strategy.py.

## How to use

1. Prepare 1‑minute intraday CSV files (or replace the stub in `fetch_intraday_kiwoom` with your Kiwoom API call).
   Example path: `/home/june/trading/data/intraday/A042660_20260601.csv`
   Columns required: time,open,high,low,close,volume
   `time` should be parseable by pandas (e.g., "2026-06-01 09:00:00").

2. Run the script:
   ```bash
   python3 rsi_cci_strategy.py --code A042660 --date 20260601 --show-plots
   ```
   - `--code` : stock code with or without leading 'A' (e.g., A042660 or 042660)
   - `--date` : YYYYMMDD format
   - `--show-plots` : optional, displays a matplotlib chart with signals

3. The script prints entry (red arrow) and exit (blue arrow) signals with timestamp, price, RSI, CCI values.

4. To actually place orders via Kiwoom, uncomment the order‑placement section at the bottom of `rsi_cci_strategy.py` and ensure your Kiwoom credentials are set in `.env` (same as `monitor_profit_exit.py`).

## Customisation

- Adjust RSI/CCI periods via `--rsi-period` and `--cci-period`.
- Change the moving‑average filter period with `--ma-period`.
- Remove the MA filter by deleting the `& (df['close'] > df[f'ma{args.ma_period}'])` and similar lines in the signal definitions.

## Next steps

- Run a walk‑forward or batch backtest over multiple days.
- Integrate the signal detection into your existing trading engine or cron job.
- Set up alerts (Telegram, etc.) when a signal occurs.

If you need help preparing the intraday data or wiring the order execution, just let me know! 