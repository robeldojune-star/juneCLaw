#!/usr/bin/env python3
"""
RSI-CCI basado signal strategy (entry/exit) for 1‑minute Kiwoom data.

Entry (red arrow):
    - RSI < 30 (oversold)
    - CCI < -100 (oversold)
    - Optional: price > short‑term moving average (e.g., MA5) to confirm
    - Signal triggers when both conditions become true on a new bar.

Exit (blue arrow):
    - RSI > 70 (overbought)
    - CCI > 100 (overbought)
    - Optional: price < short‑term moving average
    - Signal triggers when both conditions become true on a new bar.

The script:
    1. Loads 1‑minute OHLCV data for a given stock code from Kiwoom (via
       existing helper `fetch_intraday` or a local CSV fallback).
    2. Computes RSI (14) and CCI (20, typical).
    3. Detects entry/exit points.
    4. Prints signals and can optionally place market orders via
       Kiwoom kt10000/kt10001 (commented out for safety).

Usage:
    python3 rsi_cci_strategy.py --code A042660 --date 2026-06-01
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# Helper: compute RSI (Wilder's smoothing)
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(com=period - 1, adjust=False).mean()
    ma_down = down.ewm(com=period - 1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))


# Helper: compute CCI (Typical Price, 20-period, 0.015 constant)
def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    tp = (high + low + close) / 3
    ma = tp.rolling(window=period).mean()
    md = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - ma) / (0.015 * md)


# ----------------------------------------------------------------------
# Placeholder for Kiwoom intraday fetch – replace with your actual implementation
def fetch_intraday_kiwoom(stock_code: str, date: str) -> pd.DataFrame:
    """
    Return a DataFrame with columns ['time','open','high','low','close','volume']
    for 1‑minute bars of `stock_code` on `date` (YYYYMMDD) from Kiwoom.
    This is a stub; you should plug in your existing Kiwoom API call
    (e.g., using ka10006 or similar).
    """
    # Example: try to read a pre‑saved CSV if available (for testing)
    csv_path = Path(f"/home/june/trading/data/intraday/{stock_code}_{date}.csv")
    if csv_path.exists():
        df = pd.read_csv(csv_path, parse_dates=['time'])
        return df

    # If you have a function like `get_ka10006` from your codebase, import and use it:
    # from some_module import get_ka10006
    # raw = get_ka10006(stock_code, date)
    # df = pd.DataFrame(raw, columns=['time','open','high','low','close','volume'])
    # return df

    raise FileNotFoundError(
        f"Intraday data not found for {stock_code} on {date}. "
        f"Either place a CSV at {csv_path} or implement the Kiwoom fetch."
    )


# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="RSI‑CCI entry/exit signal detector")
    parser.add_argument(
        "--code",
        required=True,
        help="Stock code with optional leading 'A' (e.g., A042660 or 042660)",
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Date for intraday data in YYYYMMDD format (e.g., 20260601)",
    )
    parser.add_argument(
        "--ma-period",
        type=int,
        default=5,
        help="Short‑term moving average period for trend filter (default: 5)",
    )
    parser.add_argument(
        "--rsi-period",
        type=int,
        default=14,
        help="RSI period (default: 14)",
    )
    parser.add_argument(
        "--cci-period",
        type=int,
        default=20,
        help="CCI period (default: 20)",
    )
    parser.add_argument(
        "--show-plots",
        action="store_true",
        help="If matplotlib is available, plot price with signals",
    )
    args = parser.parse_args()

    # Normalize stock code (strip leading 'A')
    code = args.code.lstrip('A')
    if not code.isdigit() or len(code) != 6:
        sys.exit("Error: stock code must be a 6‑digit number (with or without leading 'A')")

    # Load data
    try:
        df = fetch_intraday_kiwoom(code, args.date)
    except Exception as e:
        sys.exit(f"Failed to load intraday data: {e}")

    # Ensure required columns exist
    required = {'time', 'open', 'high', 'low', 'close', 'volume'}
    if not required.issubset(set(df.columns)):
        sys.exit(f"DataFrame must contain columns: {required}")

    df = df.sort_values('time').reset_index(drop=True)

    # Calculate indicators
    df['rsi'] = rsi(df['close'], period=args.rsi_period)
    df['cci'] = cci(df['high'], df['low'], df['close'], period=args.cci_period)
    df[f'ma{args.ma_period}'] = df['close'].rolling(window=args.ma_period).mean()

    # Generate raw signals (condition becomes True)
    df['entry_raw'] = (df['rsi'] < 30) & (df['cci'] < -100) & (df['close'] > df[f'ma{args.ma_period}'])
    df['exit_raw']  = (df['rsi'] > 70) & (df['cci'] > 100) & (df['close'] < df[f'ma{args.ma_period}'])

    # Convert to edge‑triggered signals (only on the bar where condition turns True)
    df['entry_signal'] = df['entry_raw'] & (~df['entry_raw'].shift(1).fillna(False))
    df['exit_signal']  = df['exit_raw']  & (~df['exit_raw'].shift(1).fillna(False))

    # Display signals
    signals = df[df['entry_signal'] | df['exit_signal']][['time', 'close', 'rsi', 'cci', f'ma{args.ma_period}', 'entry_signal', 'exit_signal']]
    if signals.empty:
        print("No entry/exit signals found for the given period.")
    else:
        print("\n=== Detected Signals ===")
        for _, row in signals.iterrows():
            t = row['time']
            price = row['close']
            if row['entry_signal']:
                print(f"[{t}] ENTRY (red arrow)  | Price: {price:,.0f} | RSI: {row['rsi']:.2f} | CCI: {row['cci']:.2f}")
            if row['exit_signal']:
                print(f"[{t}] EXIT  (blue arrow) | Price: {price:,.0f} | RSI: {row['rsi']:.2f} | CCI: {row['cci']:.2f}")

    # Optional plotting
    if args.show_plots:
        try:
            import matplotlib.pyplot as plt
            fig, ax1 = plt.subplots(figsize=(14, 8))
            ax1.plot(df['time'], df['close'], label='Close', color='black')
            ax1.plot(df['time'], df[f'ma{args.ma_period}'], label=f'MA{args.ma_period}', color='blue', alpha=0.7)
            ax1.scatter(df.loc[df['entry_signal'], 'time'],
                        df.loc[df['entry_signal'], 'close'],
                        marker='^', color='red', s=100, label='Entry (red arrow)')
            ax1.scatter(df.loc[df['exit_signal'], 'time'],
                        df.loc[df['exit_signal'], 'close'],
                        marker='v', color='blue', s=100, label='Exit (blue arrow)')
            ax1.set_ylabel('Price')
            ax1.legend(loc='upper left')
            ax2 = ax1.twinx()
            ax2.plot(df['time'], df['rsi'], label='RSI', color='purple', alpha=0.5)
            ax2.plot(df['time'], df['cci'], label='CCI', color='brown', alpha=0.5)
            ax2.axhline(30, linestyle='--', color='purple', alpha=0.3)
            ax2.axhline(70, linestyle='--', color='purple', alpha=0.3)
            ax2.axhline(-100, linestyle='--', color='brown', alpha=0.3)
            ax2.axhline(100, linestyle='--', color='brown', alpha=0.3)
            ax2.set_ylabel('RSI / CCI')
            ax2.legend(loc='upper right')
            plt.title(f"{code} 1‑min RSI‑CCI Signals ({args.date})")
            plt.tight_layout()
            plt.show()
        except ImportError:
            print("Matplotlib not installed; skipping plot.")

    # ------------------------------------------------------------------
    # If you want to actually place orders, uncomment and adapt the
    # following section.  It uses the same Kiwoom API as monitor_profit_exit.py.
    #
    # from monitor_profit_exit import KiwoomMonitor  # assuming you have that class
    # monitor = KiwoomMonitor()
    #
    # for _, row in df.iterrows():
    #     if row['entry_signal']:
    #         # Example: buy at market price (you may want to limit size, check funds, etc.)
    #         # monitor.place_market_buy(row['code'], quantity)  # you need to implement buy
    #         pass
    #     if row['exit_signal']:
    #         # Example: sell existing position
    #         # monitor.place_market_sell(row['code'], quantity)
    #         pass

if __name__ == "__main__":
    main()