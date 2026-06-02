#!/usr/bin/env python3
"""
Unified strategy runner.
Usage:
    python3 scripts/run_strategy.py --env mock|prod [--stock 042660] [--lookback 5] [--profit-target 1.5] [--execute]
"""

import sys
import os
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

# Ensure we can import shared modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategy import compute_indicators, generate_signals
from order import place_market_order, get_available_cash
from notify import send_telegram

# Kiwoom client
from core.kiwoom_client import KiwoomAPIClient
from core.market_data_service import MarketDataService
from dotenv import load_dotenv
from datetime import datetime, timedelta

def log_signal(stock, sig_type, price, profit=None):
    """Append a signal/trade to the shared signals CSV for the dashboard."""
    dashboard_dir = Path(__file__).resolve().parents[1] / "dashboard"
    data_dir = dashboard_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    signal_file = data_dir / "signals.csv"
    df = pd.DataFrame([{
        'time': datetime.now().strftime('%Y%m%d%H%M%S'),
        'stock': stock,
        'type': sig_type,   # 'BUY' or 'SELL'
        'price': price,
        'profit': profit
    }])
    header = not signal_file.exists()
    df.to_csv(signal_file, mode='a', header=header, index=False)

def load_environment(env_name: str):
    """Load the appropriate .env file based on env_name (mock or prod)."""
    base_dir = Path(__file__).resolve().parents[1]
    env_path = base_dir / "envs" / env_name / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found: {env_path}")
    load_dotenv(dotenv_path=env_path, override=True)
    # Also set TRADING_ENV if not already in file
    os.environ["TRADING_ENV"] = env_name
    print(f"Loaded environment from: {env_path}")

def fetch_minute_data(client: KiwoomAPIClient, mkt: MarketDataService, stock_code: str, target_date_str: str, lookback_days: int) -> pd.DataFrame:
    """
    Fetch minute data for target_date_str, including previous day for warmup.
    Returns DataFrame with columns: time, open, high, low, close, volume.
    """
    target_dt = datetime.strptime(target_date_str, "%Y%m%d")
    prev_dt = target_dt - timedelta(days=1)
    prev_date_str = prev_dt.strftime("%Y%m%d")
    
    bars_target = mkt.get_minute_chart_raw(stock_code, base_dt=target_date_str, minute_scope='1', adjusted_price=True)
    bars_prev = mkt.get_minute_chart_raw(stock_code, base_dt=prev_date_str, minute_scope='1', adjusted_price=True) if prev_dt >= datetime(2020,1,1) else []
    
    bars_all = (bars_prev or []) + (bars_target or [])
    if not bars_all:
        return pd.DataFrame()
    
    df = pd.DataFrame(bars_all)
    df = df.rename(columns={
        'cntr_tm': 'time',
        'open_pric': 'open',
        'high_pric': 'high',
        'low_pric': 'low',
        'cur_prc': 'close',
        'trde_qty': 'volume'
    })
    df = df[['time','open','high','low','close','volume']]
    for col in ['open','high','low','close','volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['time'] = pd.to_datetime(df['time'], format='%Y%m%d%H%M%S')
    df = df.sort_values('time').reset_index(drop=True)
    return df

def process_day(client: KiwoomAPIClient, mkt: MarketDataService, stock_code: str, target_date_str: str, 
                profit_target: float, execute: bool, quantity: int) -> list:
    """
    Process a single day: generate signals, simulate or execute trades.
    Returns list of trade dicts for the day.
    """
    df = fetch_minute_data(client, mkt, stock_code, target_date_str, lookback_days=5)  # lookback handled inside fetch
    if df.empty:
        print(f"No data for {target_date_str}")
        return []
    
    df = compute_indicators(df)
    df = generate_signals(df)
    
    # Filter to target date only (remove previous day warmup rows)
    target_date = datetime.strptime(target_date_str, "%Y%m%d").date()
    df_target = df[df['time'].dt.date == target_date]
    
    trades = []
    in_position = False
    entry_price = None
    entry_time = None
    
    for idx, row in df_target.iterrows():
        if row['buy_signal'] and not in_position:
            in_position = True
            entry_price = row['close']
            entry_time = row['time']
            print(f"[{target_date_str}] BUY signal at {entry_time} price {entry_price:.0f}")
            if execute:
                # Determine quantity: use all available cash or fixed?
                # For simplicity, use fixed quantity param
                qty = quantity
                # Optionally check cash
                cash = get_available_cash(client)
                if cash is not None:
                    # Assume price ~ close, lots of 1 share? We'll just use quantity param
                    pass
                resp = place_market_order(client, stock_code, qty, is_buy=True)
                # Could extract order number etc.
                send_telegram(f"BUY {stock_code} qty={qty} at market")
                log_signal(stock_code, 'BUY', entry_price)
            else:
                log_signal(stock_code, 'BUY', entry_price)
        elif in_position:
            # Check profit target
            profit_pct = (row['close'] - entry_price) / entry_price * 100.0
            if profit_pct >= profit_target:
                # Sell
                exit_price = row['close']
                exit_time = row['time']
                print(f"[{target_date_str}] SELL signal (target reached) at {exit_time} price {exit_price:.0f} profit {profit_pct:.2f}%")
                trades.append({
                    'date': target_date_str,
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'exit_time': exit_time,
                    'exit_price': exit_price,
                    'profit_pct': profit_pct
                })
                if execute:
                    qty = quantity  # same quantity
                    resp = place_market_order(client, stock_code, qty, is_buy=False)
                    send_telegram(f"SELL {stock_code} qty={qty} at market profit {profit_pct:.2f}%")
                in_position = False
                entry_price = None
                entry_time = None
                log_signal(stock_code, 'SELL', exit_price, profit_pct)
            # optional: could also add stop loss logic here
    # If position remains open at end of day, we could close at market close, but we ignore for now.
    return trades

def main():
    parser = argparse.ArgumentParser(description='Run RSI/CCI disparity strategy with optional order execution.')
    parser.add_argument('--env', choices=['mock','prod'], required=True, help='Environment to use (mock or prod)')
    parser.add_argument('--stock', type=str, default='042660', help='Stock 6-digit code')
    parser.add_argument('--lookback', type=int, default=5, help='Number of lookback days for warmup')
    parser.add_argument('--profit-target', type=float, default=1.5, help='Target profit percent for exit')
    parser.add_argument('--execute', action='store_true', help='If set, place real orders; otherwise dry-run only')
    parser.add_argument('--quantity', type=int, default=1, help='Order quantity (shares)')
    args = parser.parse_args()
    
    # Load environment
    try:
        load_environment(args.env)
    except Exception as e:
        print(f"Failed to load environment: {e}")
        sys.exit(1)
    
    # Initialize Kiwoom client and market data service
    try:
        client = KiwoomAPIClient.from_env()
        mkt = MarketDataService(client)
        print(f"Kiwoom client initialized for env: {os.getenv('TRADING_ENV')}")
    except Exception as e:
        print(f"Failed to initialize Kiwoom client: {e}")
        sys.exit(1)
    
    # Determine date range: we will process recent N days (lookback days) ending today.
    # For simplicity, we process the last N trading days (excluding weekends) but we will just iterate over calendar days and skip if no data.
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=args.lookback*2)  # rough buffer to capture enough trading days
    
    all_trades = []
    current = start_date
    while current <= end_date:
        date_str = current.strftime("%Y%m%d")
        # Skip weekends? Kiwoom will return empty data, we just process.
        trades = process_day(client, mkt, args.stock, date_str, args.profit_target, args.execute, args.quantity)
        all_trades.extend(trades)
        current += timedelta(days=1)
    
    print("\n=== Summary ===")
    print(f"Total trades executed/simulated: {len(all_trades)}")
    if all_trades:
        profits = [t['profit_pct'] for t in all_trades]
        win_rate = sum(1 for p in profits if p > 0) / len(profits) * 100
        avg_profit = np.mean(profits)
        print(f"Win rate: {win_rate:.2f}%")
        print(f"Average profit per trade: {avg_profit:.2f}%")
        print(f"Profits: {[round(p,2) for p in profits]}")
    else:
        print("No trades.")
    
if __name__ == "__main__":
    main()