#!/usr/bin/env python3
"""
Compute composite signal score for KOSPI stocks based on:
- Disclosure type weights (from OpenDART)
- Foreign/Institutional net buying vs individual (from Kiwoom ka10005)
- Volume z-score (20-day MA) from daily prices

Outputs top scoring stocks for a given date.
"""
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
# Add Kiwoom API template assets directory
KIWOOM_TEMPLATE_ASSETS = PROJECT_ROOT / '.hermes' / 'skills' / '.openclaw' / 'skills' / 'kiwoom-api' / 'assets'
if KIWOOM_TEMPLATE_ASSETS.exists():
    sys.path.insert(0, str(KIWOOM_TEMPLATE_ASSETS))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from core.supabase_rest import SupabaseRestClient
from core.kiwoom_client import KiwoomAPIClient


def get_trading_env() -> str:
    """Determine trading mode from .env"""
    env = os.getenv('TRADING_ENV', 'mock').lower()
    if env not in ('mock', 'prod'):
        raise ValueError(f"TRADING_ENV must be 'mock' or 'prod', got {env}")
    return env


def load_disclosure_weights() -> Dict[str, int]:
    """Load disclosure type weights from YAML"""
    weight_file = PROJECT_ROOT / 'references' / 'disclosure_weights.yaml'
    with open(weight_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data.get('weights', {})


def get_previous_trading_day(base_date: datetime) -> str:
    """Return previous trading day as YYYYMMDD, skipping weekends"""
    # Simple: subtract 1 day; if Sat/Fri adjust? For now just -1
    prev = base_date - timedelta(days=1)
    # TODO: skip weekends and holidays using kospi calendar
    return prev.strftime('%Y%m%d')


def get_active_kospi_stocks(sb: SupabaseRestClient) -> List[Dict[str, str]]:
    """Fetch active KOSPI stocks from kospi_top50 table"""
    params = {'is_active': 'eq.True', 'select': 'stock_code,stock_name'}
    rows = sb.get('kospi_top50', params=params)
    return [{'code': r['stock_code'], 'name': r['stock_name']} for r in rows]


def get_disclosure_score(stock_code: str, target_date: str, sb: SupabaseRestClient, weights: Dict[str, int]) -> int:
    """
    Sum weights of disclosure types for a stock on target_date.
    target_date format: YYYYMMDD
    """
    # Fetch disclosures for this stock on this date
    params = {
        'stock_code': f'eq.{stock_code}',
        'rcept_dt': f'eq.{target_date}'
    }
    rows = sb.get('dart_disclosures', params=params)
    score = 0
    for r in rows:
        report_nm = r.get('report_nm', '').strip()
        # Find matching weight (exact match or substring?)
        weight = 0
        for kw, w in weights.items():
            if kw in report_nm:
                weight = w
                break
        # If no keyword matched, use default weight for '기타' or 0
        if weight == 0:
            weight = weights.get('기타', 0)
        score += weight
    return score


def get_flow_score(stock_code: str, target_date: str, kiwoom: KiwoomAPIClient) -> float:
    """
    Compute flow score from foreign + institutional net buying - individual net buying.
    Uses ka10005 (주식일주월시분요청) which returns daily lines.
    We need the line for target_date.
    Returns raw net sentiment (foreign + inst - ind).
    """
    token = kiwoom.issue_token()
    base_url = kiwoom.config.base_url
    headers = {
        'authorization': f'Bearer {token}',
        'Content-Type': 'application/json;charset=UTF-8',
        'api-id': 'ka10005'
    }
    body = {
        'stk_cd': stock_code,
        'base_dt': target_date,
        'upd_stkpc_tp': '1'  # adjusted price
    }
    try:
        import requests
        resp = requests.post(f'{base_url}/api/dostk/mrkcond', headers=headers, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('return_code') != 0:
            print(f"  ka10005 error for {stock_code}: {data.get('return_msg')}")
            return 0.0
        # Response key is stk_ddwkmm (일주월시분요청)
        rows = data.get('data', {}).get('stk_ddwkmm', [])
        if not rows:
            print(f"  ka10005 no data for {stock_code} on {target_date}")
            return 0.0
        # Find the row matching target_date (ka10005 may return multiple periods)
        # Assume first row is the daily line? We'll look for matching date.
        for row in rows:
            if row.get('date') == target_date:
                foreign = float(row.get('for_netprps', 0) or 0)
                inst = float(row.get('orgn_netprps', 0) or 0)
                ind = float(row.get('ind_netprps', 0) or 0)
                return foreign + inst - ind
        # If not found, use first row
        row = rows[0]
        foreign = float(row.get('for_netprps', 0) or 0)
        inst = float(row.get('orgn_netprps', 0) or 0)
        ind = float(row.get('ind_netprps', 0) or 0)
        return foreign + inst - ind
    except Exception as e:
        print(f"  Exception in flow score for {stock_code}: {e}")
        return 0.0


def get_volume_score(stock_code: str, target_date: str, sb: SupabaseRestClient) -> float:
    """
    Compute volume z-score: (volume_t - MA20) / stddev20
    using daily_prices table.
    Returns z-score.
    """
    # Fetch last 21 days including target_date
    params = {
        'stock_code': f'eq.{stock_code}',
        'date': f'gte.{target_date}',  # we'll get >= target_date and sort descending
        'order': 'date.desc',
        'limit': '21'
    }
    rows = sb.get('daily_prices', params=params)
    if len(rows) < 2:
        return 0.0
    # Sort ascending by date
    rows_sorted = sorted(rows, key=lambda x: x['date'])
    # Extract volumes as int
    volumes = [int(r['volume']) for r in rows_sorted if r.get('volume') is not None]
    if len(volumes) < 2:
        return 0.0
    today_vol = volumes[-1]
    # Use previous 20 days for MA and std
    if len(volumes) >= 21:
        prev_volumes = volumes[-21:-1]  # 20 days before today
    else:
        prev_volumes = volumes[:-1]  # whatever we have
    if len(prev_volumes) < 2:
        return 0.0
    import statistics
    mean_vol = statistics.mean(prev_volumes)
    stdev_vol = statistics.stdev(prev_volumes) if len(prev_volumes) >= 2 else 0.0
    if stdev_vol == 0:
        return 0.0
    z = (today_vol - mean_vol) / stdev_vol
    return z


def compute_total_score(stock_code: str, target_date: str,
                       sb: SupabaseRestClient,
                       kiwoom: KiwoomAPIClient,
                       weights: Dict[str, int],
                       w_disclosure: float = 0.4,
                       w_flow: float = 0.4,
                       w_volume: float = 0.2) -> Dict[str, Any]:
    """Compute component scores and weighted total"""
    disclosure = get_disclosure_score(stock_code, target_date, sb, weights)
    flow = get_flow_score(stock_code, target_date, kiwoom)
    volume = get_volume_score(stock_code, target_date, sb)
    # Normalize each component to 0-100 scale? For now keep raw and weight
    total = w_disclosure * disclosure + w_flow * flow + w_volume * volume
    return {
        'stock_code': stock_code,
        'date': target_date,
        'disclosure_score': disclosure,
        'flow_score': flow,
        'volume_score': volume,
        'total_score': total
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Compute signal score for KOSPI stocks')
    parser.add_argument('--date', type=str, help='Target date YYYYMMDD (default: today)')
    parser.add_argument('--top', type=int, default=10, help='Number of top stocks to show')
    parser.add_argument('--use-mock', action='store_true', help='Force use mock Kiwoom env')
    args = parser.parse_args()

    if args.date:
        target_date = args.date
        if len(target_date) != 8 or not target_date.isdigit():
            raise ValueError('Date must be YYYYMMDD')
    else:
        target_date = datetime.now().strftime('%Y%m%d')

    # Use previous trading day for signal (disclosures after close affect next day)
    # For simplicity we use same day; user can adjust.
    signal_date = target_date  # change to get_previous_trading_day if needed

    sb = SupabaseRestClient()
    # Initialize Kiwoom client
    if args.use_mock:
        kiwoom = KiwoomAPIClient.from_env(trading_env='mock')
    else:
        kiwoom = KiwoomAPIClient.from_env()  # reads from .env
    # market = MarketDataService(kiwoom)  # not used directly but could be

    weights = load_disclosure_weights()
    print(f"Loaded {len(weights)} disclosure type weights")
    print(f"Computing scores for date {signal_date}...")

    stocks = get_active_kospi_stocks(sb)
    print(f"Found {len(stocks)} active KOSPI stocks")

    results = []
    for i, stock in enumerate(stocks, 1):
        code = stock['code']
        name = stock['name']
        if i % 10 == 0 or i == len(stocks):
            print(f"  Progress: {i}/{len(stocks)}")
        try:
            score_dict = compute_total_score(code, signal_date, sb, kiwoom, weights)
            score_dict['stock_name'] = name
            results.append(score_dict)
        except Exception as e:
            print(f"  Error processing {code}: {e}")
            continue

    # Sort by total_score descending
    results.sort(key=lambda x: x['total_score'], reverse=True)
    top_n = results[:args.top]

    print("\n=== Top Signals ===")
    print(f"Date: {signal_date}")
    print(f"{'Rank':<4} {'Code':<6} {'Name':<20} {'Total':<8} {'Disc':<6} {'Flow':<8} {'Vol':<6}")
    print("-" * 60)
    for r in top_n:
        print(f"{r['stock_code']:<6} {r['stock_name']:<20} {r['total_score']:<8.2f} "
              f"{r['disclosure_score']:<6} {r['flow_score']:<8.2f} {r['volume_score']:<6.2f}")

    # Optionally save to CSV
    # import csv
    # with open(f'signals_{signal_date}.csv', 'w', newline='', encoding='utf-8') as f:
    #     writer = csv.DictWriter(f, fieldnames=['stock_code','stock_name','date','total_score','disclosure_score','flow_score','volume_score'])
    #     writer.writeheader()
    #     writer.writerows(results)


if __name__ == '__main__':
    main()