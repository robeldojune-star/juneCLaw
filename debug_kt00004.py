#!/usr/bin/env python3
import os
import httpx
from dotenv import load_dotenv
load_dotenv()
API_KEY = os.getenv('KIWOOM_REST_API_KEY')
API_SECRET = os.getenv('KIWOOM_REST_API_SECRET')
ACCOUNT_NO = os.getenv('KIWOOM_ACCOUNT_NO')
TRADING_ENV = os.getenv('TRADING_ENV', 'mock').lower()
BASE_URL = "https://mockapi.kiwoom.com" if TRADING_ENV == "mock" else "https://api.kiwoom.com"
def get_token():
    url = f"{BASE_URL}/oauth2/token"
    headers = {"Content-Type": "application/json;charset=UTF-8", "Accept": "application/json"}
    data = {"grant_type": "client_credentials", "appkey": API_KEY, "secretkey": API_SECRET}
    resp = httpx.post(url, headers=headers, json=data, timeout=10.0)
    result = resp.json()
    if result.get('return_code') == 0:
        token = result.get('token')
        return token
    else:
        raise Exception(f"Token failed: {result.get('return_msg')}")
def main():
    token = get_token()
    url = f"{BASE_URL}/api/dostk/acnt"
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'api-id': 'kt00004',
        'cont-yn': 'N',
        'next-key': ''
    }
    body = {"qry_tp": "1", "dmst_stex_tp": "KRX"}
    resp = httpx.post(url, headers=headers, json=body, timeout=10.0)
    result = resp.json()
    print("Return code:", result.get('return_code'))
    print("Return msg:", result.get('return_msg'))
    # Print keys
    print("Keys:", list(result.keys()))
    # If there is a data key, show its type
    if 'data' in result:
        print("Data type:", type(result['data']))
        if isinstance(result['data'], list):
            print("Data length:", len(result['data']))
            if result['data']:
                print("First item keys:", list(result['data'][0].keys()) if isinstance(result['data'][0], dict) else "not dict")
        else:
            print("Data sample:", str(result['data'])[:200])
    else:
        # No data key, show top-level items that might be lists
        for k, v in result.items():
            if isinstance(v, list):
                print(f"Key {k} is list of length {len(v)}")
                if v and isinstance(v[0], dict):
                    print(f"  First item keys: {list(v[0].keys())}")
            elif isinstance(v, dict):
                print(f"Key {k} is dict with keys: {list(v.keys())}")
if __name__ == '__main__':
    main()