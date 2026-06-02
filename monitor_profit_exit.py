#!/usr/bin/env python3
"""
monitor_profit_exit.py
- Monitors Kiwoom holdings (via kt00004) and sells when profit >= 5%
- Intended to be run periodically during market hours (e.g., every 20-30 minutes)
- Uses Kiwoom REST API with OAuth token caching
- Supports both mock and real trading via .env TRADING_ENV
- Logs to file and console
"""
import os
import time
import logging
import subprocess
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

# ---------- Configuration ----------

LOG_DIR = Path("/home/june/trading/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "profit_monitor.log"

# ---------- Logging Setup ----------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env in project root
load_dotenv(override=True)  # loads /home/june/trading/.env

TRADING_ENV = os.getenv('TRADING_ENV', 'mock').lower()
logger.info(f"Loaded .env: TRADING_ENV={TRADING_ENV}")
logger.info(f"API_KEY from env: {os.getenv('KIWOOM_REST_API_KEY')}")
logger.info(f"API_SECRET from env: {os.getenv('KIWOOM_REST_API_SECRET')}")
logger.info(f"ACCOUNT_NO from env: {os.getenv('KIWOOM_ACCOUNT_NO')}")
if TRADING_ENV == "prod":
    API_KEY = os.getenv('KIWOOM_REST_API_KEY')
    API_SECRET = os.getenv('KIWOOM_REST_API_SECRET')
    ACCOUNT_NO = os.getenv('KIWOOM_ACCOUNT_NO')
else:
    API_KEY = os.getenv('KIWOOM_REST_API_KEY_MOCK')
    API_SECRET = os.getenv('KIWOOM_REST_API_SECRET_MOCK')
    ACCOUNT_NO = os.getenv('KIWOOM_ACCOUNT_NO_MOCK')

# Validate essential configs
if not all([API_KEY, API_SECRET, ACCOUNT_NO]):
    raise RuntimeError(f"Missing Kiwoom {TRADING_ENV} API credentials in .env file")

BASE_URL = (
    "https://mockapi.kiwoom.com" if TRADING_ENV == "mock"
    else "https://api.kiwoom.com"
)

# Profit threshold for selling (percent)
PROFIT_THRESHOLD_PCT = 5.0

# ---------- Kiwoom API Client ----------

class KiwoomMonitor:
    def __init__(self):
        self.token = None
        self.token_expires = 0  # epoch seconds
        logger.info(f"KiwoomMonitor initialized: TRADING_ENV={TRADING_ENV}, BASE_URL={BASE_URL}")
        logger.info(f"API_KEY present: {bool(API_KEY)}, API_SECRET present: {bool(API_SECRET)}, ACCOUNT_NO present: {bool(ACCOUNT_NO)}")

    def _get_token(self):
        """Fetch or cache OAuth token."""
        now = time.time()
        if self.token and self.token_expires > now:
            return self.token

        url = f"{BASE_URL}/oauth2/token"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json"
        }
        data = {
            "grant_type": "client_credentials",
            "appkey": API_KEY,
            "secretkey": API_SECRET
        }

        try:
            resp = httpx.post(url, headers=headers, json=data, timeout=10.0)
            resp.raise_for_status()
            result = resp.json()
            if result.get('return_code') == 0:
                self.token = result.get('token')
                # Token valid for ~1 hour
                self.token_expires = now + 3600
                logger.info("OAuth token refreshed")
                return self.token
            else:
                msg = result.get('return_msg', 'Unknown error')
                logger.error(f"Token request failed: {msg}")
                raise Exception(f"Token error: {msg}")
        except Exception as e:
            logger.exception("Failed to obtain OAuth token")
            raise

    def _request(self, api_id: str, body: dict):
        """Make a signed POST request to Kiwoom API.
        Returns parsed JSON response.
        """
        token = self._get_token()
        # Determine endpoint
        if api_id in ('kt10000', 'kt10001'):
            url = f"{BASE_URL}/api/dostk/ordr"
        else:
            url = f"{BASE_URL}/api/dostk/acnt"

        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Authorization": f"Bearer {token}",
            "Api-ID": api_id,
            "Cont-YN": "N",
            "Next-Key": ""
        }

        try:
            resp = httpx.post(url, headers=headers, json=body, timeout=10.0)
            resp.raise_for_status()
            result = resp.json()
            if result.get('return_code') != 0:
                msg = result.get('return_msg', 'Unknown error')
                logger.warning(f"API {api_id} returned error {msg}")
            return result
        except Exception as e:
            logger.exception(f"HTTP request to {api_id} failed")
            raise

    def get_holdings(self):
        """Fetch current holdings from kt00004 (계좌평가현황).
        Returns list of holding dicts (empty list if none or error).
        """
        body = {
            "qry_tp": "1",          # 0: 총괄, 1: 상세
            "dmst_stex_tp": "KRX"   # Korean exchange
        }
        try:
            result = self._request("kt00004", body)
            if result.get('return_code') != 0:
                logger.error(f"Holdings fetch failed: {result.get('return_msg')}")
                return []
            # kt00004 returns data at top level (not under 'data' key)
            holdings = result.get('stk_acnt_evlt_prst', [])
            logger.info(f"Fetched {len(holdings)} holdings from kt00004")
            return holdings
        except Exception as e:
            logger.exception("Unexpected error while fetching holdings")
            return []

    def place_market_sell(self, stock_code: str, quantity: int):
        """Place a market sell order (kt10001) for given stock and quantity.
        Returns order number (ord_no) if successful, else None.
        """
        if quantity <= 0:
            logger.warning(f"Quantity {quantity} for {stock_code} is not positive")
            return None

        # In mock environment, stock codes may be prefixed with 'A' (e.g., A005930).
        # The API expects the raw 6-digit code without prefix.
        clean_code = stock_code.lstrip('A')
        if not clean_code.isdigit() or len(clean_code) != 6:
            logger.warning(f"Invalid stock code format: {stock_code} -> {clean_code}")
            return None

        body = {
            "dmst_stex_tp": "KRX",
            "stk_cd": clean_code,
            "ord_qty": str(int(quantity)),   # must be string
            "ord_uv": "0",                   # 0 = market price
            "trde_tp": "3"                   # 3 = market order (assumed same for buy/sell)
        }

        logger.info(f"Placing market sell: {clean_code} qty={quantity}")
        try:
            result = self._request("kt10001", body)
            if result.get('return_code') == 0:
                ord_no = result.get('ord_no')
                logger.info(f"Sell order placed: {clean_code} qty={quantity} ord_no={ord_no}")
                return ord_no
            else:
                msg = result.get('return_msg', 'Unknown error')
                logger.error(f"Sell order failed for {clean_code}: {msg}")
                return None
        except Exception as e:
            logger.exception(f"Exception while placing sell order for {clean_code}")
            return None

# ---------- Telegram Notification ----------

def send_telegram_notification(message: str):
    """Send a notification via Telegram using the Hermes CLI."""
    try:
        result = subprocess.run(
            ["hermes", "send", "--to", "telegram", message],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info(f"Telegram notification sent: {message[:100]}...")
        else:
            logger.error(f"Failed to send Telegram notification: {result.stderr}")
    except FileNotFoundError:
        logger.error("Hermes CLI not found. Cannot send Telegram notification.")
    except Exception as e:
        logger.exception("Exception while sending Telegram notification")

# ---------- Main Logic ----------

def main():
    logger.info("=== Profit-exit monitor started ===")
    logger.info(f"Environment: {TRADING_ENV}")
    logger.info(f"Profit threshold: {PROFIT_THRESHOLD_PCT}%")

    monitor = KiwoomMonitor()
    holdings = monitor.get_holdings()

    if not holdings:
        logger.info("No holdings found (or failed to fetch). Exiting.")
        return

    sold_count = 0
    skipped_count = 0

    for h in holdings:
        try:
            # Extract fields from kt00004 holding item
            code = h.get('stk_cd', '').strip()
            name = h.get('stk_nm', '').strip()
            qty_str = h.get('rmnd_qty', '0')          # 남은 수량
            avg_price_str = h.get('avg_prc', '0')     # 평균 단가
            curr_price_str = h.get('cur_prc', '0')    # 현재가
            pl_rt_str = h.get('pl_rt', '0')           # 손익율 (percentage string)

            # Convert to numeric, skip if invalid
            try:
                qty = int(qty_str)
                avg_price = float(avg_price_str)
                curr_price = float(curr_price_str)
                profit_pct = float(pl_rt_str)   # pl_rt is already percentage
            except ValueError:
                logger.warning(f"Invalid numeric for {code}: qty={qty_str}, avg={avg_price_str}, curr={curr_price_str}, pl_rt={pl_rt_str}")
                skipped_count += 1
                continue

            # Validate quantities and prices
            if qty <= 0:
                logger.debug(f"Holding {code} has zero or negative quantity: {qty}")
                skipped_count += 1
                continue
            if avg_price <= 0:
                logger.warning(f"Holding {code} has invalid average price: {avg_price}")
                skipped_count += 1
                continue

            logger.info(
                f"Holding {code} {name}: "
                f"qty={qty:,}, "
                f"avg={avg_price:,.0f}, "
                f"curr={curr_price:,.0f}, "
                f"profit%={profit_pct:.2f}%"
            )

            # Check profit threshold
            if profit_pct >= PROFIT_THRESHOLD_PCT:
                logger.info(f"Profit >= {PROFIT_THRESHOLD_PCT}% for {code} ({profit_pct:.2f}%) -> initiating sell")
                ord_no = monitor.place_market_sell(code, qty)
                if ord_no:
                    sold_count += 1
                    msg = f"✅ 매도 체결: {code} {name} 수량 {qty} 주문번호 {ord_no}"
                    send_telegram_notification(msg)
                    # Avoid hammering the API: pause briefly after each successful order
                    time.sleep(1.5)
                else:
                    logger.error(f"Failed to place sell order for {code}")
                    # Still count as attempted? We'll not increment sold_count
            else:
                logger.debug(f"Profit {profit_pct:.2f}% < threshold {PROFIT_THRESHOLD_PCT}% for {code}")

        except Exception as e:
            logger.exception(f"Unexpected error processing holding {h.get('stk_cd', 'UNKNOWN')}")
            skipped_count += 1

    # Summary
    logger.info(
        f"=== Monitor cycle complete ===\n"
        f"  Holdings processed: {len(holdings)}\n"
        f"  Sell orders placed: {sold_count}\n"
        f"  Skipped/errors: {skipped_count}"
    )

if __name__ == "__main__":
    main()