#!/usr/bin/env python3
"""
Liquidate all holdings at market price (for cleaning up before tests)
Uses same Kiwoom API as monitor_profit_exit.py but sells everything regardless of profit
"""

import os
import time
import logging
from pathlib import Path
import httpx
from dotenv import load_dotenv

# Setup logging
log_dir = Path("/home/june/trading/logs")
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "liquidate.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

TRADING_ENV = os.getenv('TRADING_ENV', 'mock').lower()
API_KEY = os.getenv('KIWOOM_REST_API_KEY')
API_SECRET = os.getenv('KIWOOM_REST_API_SECRET')
ACCOUNT_NO = os.getenv('KIWOOM_ACCOUNT_NO')

if not all([API_KEY, API_SECRET, ACCOUNT_NO]):
    logger.error("Missing Kiwoom API credentials in .env")
    raise SystemExit(1)

BASE_URL = (
    "https://mockapi.kiwoom.com" if TRADING_ENV == "mock"
    else "https://api.kiwoom.com"
)

class KiwoomLiquidator:
    def __init__(self):
        self.token = None
        self.token_expires = 0

    def _get_token(self):
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
                self.token_expires = now + 3600
                logger.info("Token refreshed")
                return self.token
            else:
                msg = result.get('return_msg', 'Unknown error')
                logger.error(f"Token failed: {msg}")
                raise Exception(f"Token error: {msg}")
        except Exception as e:
            logger.exception("Failed to get token")
            raise

    def _request(self, api_id: str, body: dict):
        token = self._get_token()
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
            logger.exception(f"Request to {api_id} failed")
            raise

    def get_holdings(self):
        body = {
            "qry_tp": "1",
            "dmst_stex_tp": "KRX"
        }
        result = self._request("kt00004", body)
        if result.get('return_code') != 0:
            logger.error(f"Holdings fetch failed: {result.get('return_msg')}")
            return []
        holdings = result.get('stk_acnt_evlt_prst', [])
        logger.info(f"Fetched {len(holdings)} holdings")
        return holdings

    def place_market_sell(self, stock_code: str, quantity: int):
        if quantity <= 0:
            logger.warning(f"Quantity {quantity} for {stock_code} is not positive")
            return None
        clean_code = stock_code.lstrip('A')
        body = {
            "dmst_stex_tp": "KRX",
            "stk_cd": clean_code,
            "ord_qty": str(int(quantity)),
            "ord_uv": "0",
            "trde_tp": "3"
        }
        logger.info(f"Placing market sell: {clean_code} qty={quantity}")
        result = self._request("kt10001", body)
        if result.get('return_code') == 0:
            ord_no = result.get('ord_no')
            logger.info(f"Sell order placed: {clean_code} qty={quantity} ord_no={ord_no}")
            return ord_no
        else:
            logger.error(f"Sell order failed for {clean_code}: {result.get('return_msg')}")
            return None

def main():
    logger.info("=== Liquidation started ===")
    logger.info(f"Environment: {TRADING_ENV}")
    
    liquidator = KiwoomLiquidator()
    holdings = liquidator.get_holdings()
    
    if not holdings:
        logger.info("No holdings to liquidate")
        return
    
    liquidated_count = 0
    failed_count = 0
    
    for h in holdings:
        try:
            code = h.get('stk_cd', '').strip()
            name = h.get('stk_nm', '').strip()
            qty_str = h.get('rmnd_qty', '0')
            
            try:
                qty = int(qty_str)
            except ValueError:
                logger.warning(f"Invalid quantity for {code}: {qty_str}")
                failed_count += 1
                continue
                
            if qty <= 0:
                logger.debug(f"Holding {code} has zero or negative quantity: {qty}")
                continue
                
            logger.info(f"Liquidating {code} {name}: qty={qty}")
            ord_no = liquidator.place_market_sell(code, qty)
            if ord_no:
                liquidated_count += 1
                time.sleep(1.5)  # Avoid rate limiting
            else:
                logger.error(f"Failed to liquidate {code}")
                failed_count += 1
                
        except Exception as e:
            logger.exception(f"Error processing holding {h.get('stk_cd', 'UNKNOWN')}")
            failed_count += 1
    
    logger.info(
        f"=== Liquidation complete ===\n"
        f"  Holdings processed: {len(holdings)}\n"
        f"  Successfully liquidated: {liquidated_count}\n"
        f"  Failed: {failed_count}"
    )
    
    # Verify liquidation
    time.sleep(3)  # Wait for orders to process
    logger.info("Verifying liquidation...")
    remaining_holdings = liquidator.get_holdings()
    remaining_count = sum(1 for h in remaining_holdings if int(h.get('rmnd_qty', '0')) > 0)
    if remaining_count == 0:
        logger.info("Verification successful: All holdings liquidated")
    else:
        logger.warning(f"Verification shows {remaining_count} holdings still remaining")

if __name__ == "__main__":
    main()