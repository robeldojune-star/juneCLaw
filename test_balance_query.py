#!/usr/bin/env python3
"""
Test real account balance query using Kiwoom kt00004 (계좌평가현황).
Does not place any orders, only queries account info.
"""
import os
import sys
import logging
import time
from datetime import datetime
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
        logging.FileHandler(log_dir / "balance_test.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()  # loads /home/june/trading/.env

TRADING_ENV = os.getenv('TRADING_ENV', 'mock').lower()
API_KEY = os.getenv('KIWOOM_REST_API_KEY')
API_SECRET = os.getenv('KIWOOM_REST_API_SECRET')
ACCOUNT_NO = os.getenv('KIWOOM_ACCOUNT_NO')

# Basic validation (do not expose values)
if not all([API_KEY, API_SECRET, ACCOUNT_NO]):
    logger.error("Missing Kiwoom API credentials in .env")
    sys.exit(1)

BASE_URL = (
    "https://mockapi.kiwoom.com" if TRADING_ENV == "mock"
    else "https://api.kiwoom.com"
)

class KiwoomBalanceChecker:
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

    def get_account_evaluation(self):
        """Fetch account evaluation (kt00004) and return dict."""
        body = {
            "qry_tp": "0",          # 0:총괄, 1:상세
            "dmst_stex_tp": "KRX"
        }
        try:
            result = self._request("kt00004", body)
            if result.get('return_code') != 0:
                logger.error(f"Account evaluation failed: {result.get('return_msg')}")
                return None
            # kt00004 returns data at top level, not under 'data' key
            return result
        except Exception as e:
            logger.exception("Unexpected error while fetching account evaluation")
            return None

    def get_holdings(self):
        """Return list of holdings from kt00004 (상세)."""
        body = {
            "qry_tp": "1",          # 0:총괄, 1:상세
            "dmst_stex_tp": "KRX"
        }
        try:
            result = self._request("kt00004", body)
            if result.get('return_code') != 0:
                logger.error(f"Holdings fetch failed: {result.get('return_msg')}")
                return []
            holdings = result.get('stk_acnt_evlt_prst', [])
            logger.info(f"Fetched {len(holdings)} holdings")
            return holdings
        except Exception as e:
            logger.exception("Unexpected error while fetching holdings")
            return []

def main():
    logger.info("=== Starting balance query test ===")
    logger.info(f"Environment: {TRADING_ENV}")
    logger.info(f"Time: {datetime.now()}")

    checker = KiwoomBalanceChecker()
    # Get account evaluation
    acc_eval = checker.get_account_evaluation()
    if acc_eval is None:
        logger.error("Failed to retrieve account evaluation.")
        return

    # Extract useful fields (masking sensitive info if any)
    # Fields from kt00004: acnt_nm, brch_nm, entr, d2_entra, tot_est_amt, aset_evlt_amt, etc.
    # We'll log a summary.
    logger.info("Account evaluation summary:")
    for key in ['acnt_nm', 'brch_nm', 'entr', 'tot_est_amt', 'aset_evlt_amt', 'tot_pur_amt', 'pl_amt']:
        if key in acc_eval:
            logger.info(f"  {key}: {acc_eval[key]}")

    # Get holdings
    holdings = checker.get_holdings()
    if holdings:
        logger.info(f"Holdings count: {len(holdings)}")
        for i, h in enumerate(holdings[:5]):  # Show first 5
            code = h.get('stk_cd', '').strip()
            name = h.get('stk_nm', '').strip()
            qty = h.get('rmnd_qty', '0')
            avg_price = h.get('avg_prc', '0')
            curr_price = h.get('cur_prc', '0')
            pl_rt = h.get('pl_rt', '0')
            logger.info(f"  Holding {i+1}: {code} {name} qty={qty} avg={avg_price} curr={curr_price} pl%={pl_rt}")
        if len(holdings) > 5:
            logger.info(f"  ... and {len(holdings)-5} more holdings")
    else:
        logger.info("No holdings found.")

    logger.info("=== Balance query test completed ===")

if __name__ == "__main__":
    main()