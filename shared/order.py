# shared/order.py
# Wrapper for Kiwoom order APIs (kt10000 buy, kt10001 sell)
# Assumes a KiwoomAPIClient instance is passed in.

from typing import Optional
import logging

logger = logging.getLogger(__name__)

def place_market_order(client, stock_code: str, qty: int, is_buy: bool, 
                       price: int = 0, order_type: str = "01") -> dict:
    """
    Place a market order via Kiwoom REST.
    Parameters:
        client: KiwoomAPIClient instance (already configured for mock or prod)
        stock_code: 6-digit string (e.g., "042660")
        qty: order quantity (positive integer)
        is_buy: True for buy, False for sell
        price: price for limit order; 0 means market order (Kiwoom spec)
        order_type: "01" for buy, "02" for sell (refer to Kiwoom API docs)
    Returns:
        dict: the raw JSON response from Kiwoom
    """
    # Determine api-id
    api_id = "kt10000" if is_buy else "kt10001"
    # Body per Kiwoom REST API for stock order
    body = {
        "dmst_stex_tp": "KRX",
        "stk_cd": stock_code,
        "ord_qty": str(qty),
        "ord_uv": str(price),  # 0 for market
        "trde_tp": "3",        # 0:지정가, 3:시장가 (market)
        "cond_uv": ""          # not used
    }
    # Note: Kiwoom may require additional fields like "ord_dvsn": "00" etc. Adjust per your tested version.
    logger.info(f"Placing {'BUY' if is_buy else 'SELL'} order: code={stock_code}, qty={qty}, price={price}")
    try:
        resp = client.post(api_id, "/api/dostk/ordr", body)
        if resp.ok:
            logger.info(f"Order placed successfully: {resp.data}")
        else:
            logger.error(f"Order failed: {resp.return_msg}")
        return resp.data
    except Exception as e:
        logger.exception(f"Exception while placing order: {e}")
        raise

def get_available_cash(client) -> Optional[int]:
    """
    Query available cash (예수금) via kt00004.
    Returns integer amount or None on failure.
    """
    try:
        # Using kt00004 with qry_tp=0 (summary)
        body = {"qry_tp": "0", "dmst_stex_tp": "KRX"}
        resp = client.post("kt00004", "/api/dostk/acnt", body)
        if resp.ok:
            # Field name may vary; common: dnca_exkg (주문가능금액)
            cash = resp.data.get("dnca_exkg")
            if cash is not None:
                return int(cash)
            # fallback: tot_est_amt - aset_evlt_amt? Not needed.
        else:
            logger.warning(f"Failed to get cash: {resp.return_msg}")
    except Exception as e:
        logger.exception(f"Error fetching cash: {e}")
    return None