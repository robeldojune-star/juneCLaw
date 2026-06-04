#!/usr/bin/env python3
"""
Unified runner for RSI/CCI disparity strategy with mock/prod separation.
Fetches minute data via Kiwoom API and generates signals per minute.
Writes signals to a CSV file for the dashboard.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# Add the project root to sys.path so we can import shared modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.strategy import compute_indicators, generate_signals, generate_signals_profit_target
from shared.order import place_market_order, get_available_cash
from shared.notify import send_telegram
from core.kiwoom_client import KiwoomAPIClient
from core.market_data_service import MarketDataService
from dotenv import load_dotenv


def parse_args():
    parser = argparse.ArgumentParser(description='Run RSI/CCI disparity strategy')
    parser.add_argument('--env', choices=['mock', 'prod'], required=True,
                        help='Environment to use (mock or prod)')
    parser.add_argument('--stock', type=str, nargs='+', required=True,
                        help='Stock code(s) (6 digits, e.g., 042660 005930)')
    parser.add_argument('--lookback', type=int, default=5,
                        help='Number of days to look back for warmup (default: 5)')
    parser.add_argument('--profit-target', type=float, default=1.5,
                        help='Profit target percentage for optional exit (default: 1.5%)')
    parser.add_argument('--execute', action='store_true',
                        help='If set, place real orders; otherwise dry-run')
    parser.add_argument('--quantity', type=int, default=1,
                        help='Order quantity (default: 1)')
    return parser.parse_args()


def load_environment(env_name: str) -> Path:
    """Load the appropriate .env file and set TRADING_ENV."""
    env_path = PROJECT_ROOT / 'envs' / env_name / '.env'
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found: {env_path}")
    load_dotenv(dotenv_path=env_path, override=True)
    os.environ['TRADING_ENV'] = env_name
    print(f"Loaded environment: {env_name} from {env_path}")
    return env_path


def fetch_minute_data_for_date(client: KiwoomAPIClient, mkt: MarketDataService,
                               stock_code: str, date: datetime) -> pd.DataFrame:
    """
    Fetch 1-minute bar data for a given stock and date (Korean market hours).
    Uses ka10080 with base_dt=date (YYYYMMDD) and tic_scope='1'.
    Returns a DataFrame with columns: ['open','high','low','close','volume']
    and index as the time string (HHMMSS) or we can keep as column.
    """
    base_dt = date.strftime('%Y%m%d')
    try:
        raw = mkt.get_minute_chart_raw(stock_code, base_dt=base_dt, minute_scope='1', adjusted_price=True)
    except Exception as e:
        print(f"Error fetching minute data for {stock_code} on {date.date()}: {e}")
        return pd.DataFrame()
    if not raw:
        print(f"No minute data returned for {stock_code} on {date.date()}")
        return pd.DataFrame()
    # Convert to DataFrame
    df = pd.DataFrame(raw)
    # Expected keys: 'cntr_tm', 'open_pric', 'high_pric', 'low_pric', 'cur_prc', 'trde_qty'
    # Note: 'cur_prc' is the closing price for the minute bar.
    df.rename(columns={
        'open_pric': 'open',
        'high_pric': 'high',
        'low_pric': 'low',
        'cur_prc': 'close',   # current price = close for the minute
        'trde_qty': 'volume'
    }, inplace=True)
    # Ensure numeric
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    # We'll keep the time column as 'time' (string HHMMSS)
    df.rename(columns={'cntr_tm': 'time'}, inplace=True)
    # Sort by time ascending
    df = df.sort_values('time').reset_index(drop=True)
    return df


def write_signal_to_csv(signal_time: str, stock_code: str, signal_type: str, price: float, profit: str = ""):
    """
    Write a signal to the CSV file for the dashboard.
    CSV file: /home/june/trading/dash-kiwoom/data/signals.csv
    Columns: time, stock, type, price, profit
    """
    csv_path = PROJECT_ROOT / 'dash-kiwoom' / 'data' / 'signals.csv'
    # Ensure the directory exists
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    # Prepare the row
    row = f"{signal_time},{stock_code},{signal_type},{price},{profit}\n"
    # If file doesn't exist, write header
    if not csv_path.exists():
        with open(csv_path, 'w') as f:
            f.write("time,stock,type,price,profit\n")
    # Append the row
    with open(csv_path, 'a') as f:
        f.write(row)


def main():
    args = parse_args()
    env_path = load_environment(args.env)

    client = KiwoomAPIClient.from_env(env_path=env_path)
    mkt = MarketDataService(client)

    for stock in args.stock:
        print(f"\n=== Stock: {stock} ===")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.lookback)

        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            date_str = current_date.strftime('%Y-%m-%d')
            print(f"Processing date: {date_str}")
            df = fetch_minute_data_for_date(client, mkt, stock, current_date)
            if df.empty:
                print(f"No data for {stock} on {date_str}")
                current_date += timedelta(days=1)
                continue

            df = compute_indicators(df)
            if args.profit_target and args.profit_target > 0:
                df = generate_signals_profit_target(df, args.profit_target)
            else:
                df = generate_signals(df)

            buy_signals = df['buy_signal'].sum()
            sell_signals = df['sell_signal'].sum()
            print(f"  Buy signals: {buy_signals}, Sell signals: {sell_signals}")

            if args.execute and (buy_signals > 0 or sell_signals > 0):
                print("  Executing orders...")
                for idx, row in df.iterrows():
                    if row['buy_signal']:
                        price = int(row['close'])
                        qty = args.quantity
                        print(f"    BUY signal at {row['time']}: price={price}, qty={qty}")
                        try:
                            resp = place_market_order(client, stock, qty, is_buy=True, price=0)
                            print(f"      Order response: {resp}")
                            send_telegram(f"[{args.env.upper()}] BUY {stock} {qty} shares at market price ~{price} KRW")
                            write_signal_to_csv(row['time'], stock, 'buy', price, "")
                        except Exception as e:
                            print(f"      Order failed: {e}")
                    elif row['sell_signal']:
                        price = int(row['close'])
                        qty = args.quantity
                        print(f"    SELL signal at {row['time']}: price={price}, qty={qty}")
                        try:
                            resp = place_market_order(client, stock, qty, is_buy=False, price=0)
                            print(f"      Order response: {resp}")
                            send_telegram(f"[{args.env.upper()}] SELL {stock} {qty} shares at market price ~{price} KRW")
                            write_signal_to_csv(row['time'], stock, 'sell', price, "")
                        except Exception as e:
                            print(f"      Order failed: {e}")

            elif not args.execute and (buy_signals > 0 or sell_signals > 0):
                print("  Writing signals to CSV (dry-run)...")
                for idx, row in df.iterrows():
                    if row['buy_signal']:
                        write_signal_to_csv(row['time'], stock, 'buy', abs(float(row['close'])), "")
                    elif row['sell_signal']:
                        write_signal_to_csv(row['time'], stock, 'sell', abs(float(row['close'])), "")

            current_date += timedelta(days=1)

    print("Strategy run completed.")


if __name__ == '__main__':
    main()