# Master Plan: RSI/CCI Disparity Strategy with Mock/Prod Separation

## Overview
This plan outlines the steps to develop, test, and deploy the RSI/CCI disparity20 strategy with clear separation between mock (demo) and production (real) Kiwoom accounts, avoiding confusion and unintended orders.

## Directory Structure
- `shared/` – reusable Python modules (indicators, signal generation, order placement, notifications)
- `envs/mock/` – contains `.env` with mock Kiwoom credentials (TRADING_ENV=mock)
- `envs/prod/` – contains `.env` with production Kiwoom credentials (TRADING_ENV=prod)
- `scripts/run_strategy.py` – unified runner that loads the appropriate environment and executes the strategy (dry-run or live orders)

## Implementation Details
### Shared Modules
1. `strategy.py`
   - `compute_indicators(df)`: calculates MA20, disparity20, CCI, RSI, volume MA20.
   - `generate_signals(df)`: creates buy (disparity20<=100 & CCI crosses -100 up & volume>=MA20) and sell (RSI crosses down from >=70 to <70) signals, edge-triggered.
2. `order.py`
   - `place_market_order(client, stock_code, qty, is_buy)`: wraps kt10000/kt10001 for market orders.
   - `get_available_cash(client)`: queries kt00004 for 신용예수금 (dnca_exkg) to gauge orderable amount.
3. `notify.py`
   - `send_telegram(message)`: uses Hermes CLI to send a message to the configured Telegram chat.

### Runner Script
`scripts/run_strategy.py`
- Accepts arguments: `--env mock|prod`, `--stock`, `--lookback`, `--profit-target`, `--execute`, `--quantity`.
- Loads the appropriate `.env` from `envs/<env>/.env` via `python-dotenv`, overriding `TRADING_ENV`.
- Initializes `KiwoomAPIClient.from_env()` and `MarketDataService`.
- For each date in the lookback window:
  - fetches minute data (including previous day for warmup),
  - computes indicators,
  - generates signals,
  - simulates or executes trades based on `--execute` flag,
  - sends Telegram notifications on order placement.
- Prints summary: total trades, win rate, average profit.

## Usage Guide
### 1. Prepare Environment Files
- Edit `envs/mock/.env`:
  ```
  TRADING_ENV=mock
  KIWOOM_REST_API_KEY_MOCK=<your mock appkey>
  KIWOOM_REST_API_SECRET_MOCK=<your mock secretkey>
  KIWOOM_ACCOUNT_NO_MOCK=<your mock account number (starts with 8)>
  ```
- Edit `envs/prod/.env`:
  ```
  TRADING_ENV=prod
  KIWOOM_REST_API_KEY=<your real appkey>
  KIWOOM_REST_API_SECRET=<your real secretkey>
  KIWOOM_ACCOUNT_NO=<your real account number (starts with 3)>
  ```

### 2. Mock Validation (No Real Money)
```bash
cd /home/june/trading
python3 scripts/run_strategy.py --env mock --stock 042660 --lookback 5 --profit-target 1.5
```
- Observe buy/sell signals in the console; no orders are placed.

### 3. Mock Order Test (Optional)
```bash
python3 scripts/run_strategy.py --env mock --stock 042660 --execute --quantity 1
```
- Places actual orders in the Kiwoom mock server; verify via Kiwoom HTS/API that orders appear and telegram alerts are received.

### 4. Check Mock Balance (Optional)
```bash
TRADING_ENV=mock python3 test_balance_query.py
```
- Confirms available cash (`dnca_exkg`) and holdings.

### 5. Production Validation (Real Money – Start Small)
- Double-check that `envs/prod/.env` contains correct real credentials.
- Run a minimal size test:
```bash
python3 scripts/run_strategy.py --env prod --stock 042660 --execute --quantity 1
```
- Monitor your real account and telegram for order fills.

### 6. (Optional) Automate with Hermes Cron
Once satisfied with tests, register a cron job to run during market hours (09:00‑15:30, Mon‑Fri):
```bash
hermes cronjob create \
    --name rsi_cci_live \
    --schedule '*/1 9-15 * * 1-5' \
    --prompt "cd /home/june/trading && python3 scripts/run_strategy.py --env prod --stock 042660 --execute --quantity 1" \
    --workdir /home/june/trading \
    --deliver telegram:<your_chat_id>
```
- Adjust `--quantity` or add position sizing logic as desired.

## Safety Checks
- **Environment Separation**: Mock and prod keys are stored in distinct files; the loader picks only one based on `--env`, eliminating cross‑contamination.
- **Order Execution Guard**: Orders are sent only when `--execute` flag is present; default is dry‑run.
- **Quantity Control**: Use `--quantity` to limit order size; start with 1 share in prod.
- **Telegram Alerts**: All order attempts (mock or prod) generate a telegram message for audit.

## Next Steps / Possible Enhancements
- Add stop‑loss or trailing exit logic in `shared/strategy.py`.
- Implement dynamic position sizing based on available cash (`get_available_cash`).
- Extend the runner to handle a list of stocks (e.g., KOSPI Top 50) with lookback warmup.
- Store trade results to CSV/SQLite for performance analysis.
- Integrate with existing n8n workflows for pre‑market risk checks.

---
*Recorded: 2026-06-01*  
*Location: /home/june/trading/docs/strategies/master_plan.md*