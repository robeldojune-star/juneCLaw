#!/usr/bin/env python3
"""
Parameter optimization for Fujimoto 1-2-6 strategy using the enhanced backtest script.
"""
import sys
import itertools
import subprocess
import tempfile
import os
from pathlib import Path
import csv
import re

def run_backtest_with_params(stop_loss_pct, take_profit_half_pct, take_profit_pct):
    """Run backtest by creating a temporary modified script."""
    # Read the enhanced backtest script
    script_path = Path("/home/june/trading/backtest_fujimoto_custom_swing.py")
    with open(script_path, 'r') as f:
        content = f.read()

    # Replace the default parameter values in the simulate_custom_swing function signature
    # The function signature is long; we replace the three parameters we want to vary.
    pattern = r'def simulate_custom_swing\(bars, \*, stop_loss_pct=-1\.0, take_profit_pct=3\.0, take_profit_half_pct=5\.0, max_holding_days=3, fee_bps=23\.0, slippage_bps=10\.0, min_score=60\.0, vwap_enabled=True, volume_surge_enabled=True, volatility_range_enabled=True, time_of_day_enabled=True, bid_ask_pressure_enabled=True, volume_surge_lookback=20, volume_surge_threshold=1\.5, volatility_range_min=0\.005, volatility_range_max=0\.05, time_of_day_start="09:00", time_of_day_end="15:20", latency_bars=1, iceberg_fill_ratio=0\.1, bid_ask_pressure_threshold=0\.0\):'
    replacement = f'def simulate_custom_swing(bars, *, stop_loss_pct={stop_loss_pct}, take_profit_pct={take_profit_pct}, take_profit_half_pct={take_profit_half_pct}, max_holding_days=3, fee_bps=23.0, slippage_bps=10.0, min_score=60.0, vwap_enabled=True, volume_surge_enabled=True, volatility_range_enabled=True, time_of_day_enabled=True, bid_ask_pressure_enabled=True, volume_surge_lookback=20, volume_surge_threshold=1.5, volatility_range_min=0.005, volatility_range_max=0.05, time_of_day_start="09:00", time_of_day_end="15:20", latency_bars=1, iceberg_fill_ratio=0.1, bid_ask_pressure_threshold=0.0):'
    modified_content = re.sub(pattern, replacement, content)

    # Also reduce the scope in main() to speed up: fewer stocks and fewer days.
    # We'll replace the stock_codes line and the date range lines.
    # Find the line that sets stock_codes and change to first 5 stocks.
    modified_content = re.sub(
        r'stock_codes = KOSPI_TOP_50\[:20\]',
        'stock_codes = KOSPI_TOP_50[:5]',
        modified_content
    )
    # Find the line that sets start_date and change to end_date - 2 days (3 days total)
    modified_content = re.sub(
        r'start_date = end_date - timedelta\(days=13\)',
        'start_date = end_date - timedelta(days=2)',
        modified_content
    )

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
        tmp.write(modified_content)
        tmp_path = tmp.name

    try:
        # Run the modified script
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=60  # Timeout for each backtest
        )

        # Check if script ran successfully
        if result.returncode != 0:
            print(f"Script failed with return code {result.returncode}")
            print(f"Stderr: {result.stderr}")
            return None

        # Parse output to extract results
        output = result.stdout

        # Extract key metrics from output
        metrics = {}
        for line in output.split('\\n'):
            line = line.strip()
            if 'Total days evaluated:' in line:
                pass
            if 'Successful trades:' in line:
                try:
                    parts = line.split(':')[1].strip()
                    successful = int(parts.split('/')[0])
                    total = int(parts.split('/')[1])
                    metrics['successful_trades'] = successful
                    metrics['total_evaluated'] = total
                except:
                    pass
            if 'Average net return:' in line:
                try:
                    avg_return_str = line.split(':')[1].strip().replace('%', '')
                    metrics['avg_return'] = float(avg_return_str)
                except:
                    pass
            if 'Positive rate:' in line:
                try:
                    positive_rate_str = line.split(':')[1].strip().replace('%', '')
                    metrics['positive_rate'] = float(positive_rate_str)
                except:
                    pass
            if 'Min return:' in line:
                try:
                    min_return_str = line.split(':')[1].strip().replace('%', '')
                    metrics['min_return'] = float(min_return_str)
                except:
                    pass
            if 'Max return:' in line:
                try:
                    max_return_str = line.split(':')[1].strip().replace('%', '')
                    metrics['max_return'] = float(max_return_str)
                except:
                    pass

        # Add the parameters to the metrics
        metrics.update({
            'stop_loss_pct': stop_loss_pct,
            'take_profit_half_pct': take_profit_half_pct,
            'take_profit_pct': take_profit_pct
        })

        return metrics

    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except:
            pass

def main():
    """Run parameter optimization with a small grid for testing."""
    # Define parameter ranges (small for quick test)
    stop_loss_values = [-1.0, -1.5]  # as percent (negative)
    take_profit_half_values = [2.5, 3.5]  # first target (sell 50%)
    take_profit_values = [5.0, 6.0]   # second target (sell remaining 50%)

    print("Starting Fujimoto 1-2-6 strategy parameter optimization (enhanced script, reduced scope)...")
    print(f"Testing {len(stop_loss_values)} stop loss values: {stop_loss_values}")
    print(f"Testing {len(take_profit_half_values)} take profit half values: {take_profit_half_values}")
    print(f"Testing {len(take_profit_values)} take profit values: {take_profit_values}")
    print(f"Total combinations: {len(stop_loss_values) * len(take_profit_half_values) * len(take_profit_values)}")
    print("=" * 70)

    results = []
    count = 0

    for sl, tph, tp in itertools.product(stop_loss_values, take_profit_half_values, take_profit_values):
        count += 1
        print(f"[{count:2d}] Testing SL={sl:>4}%, TP1={tph:>4}%, TP2={tp:>4}% ... ", end="", flush=True)

        try:
            metrics = run_backtest_with_params(sl, tph, tp)
            if metrics is None:
                print(f"FAILED")
                # Add a failed result
                results.append({
                    'stop_loss_pct': sl,
                    'take_profit_half_pct': tph,
                    'take_profit_pct': tp,
                    'successful_trades': 0,
                    'total_evaluated': 0,
                    'avg_return': 0.0,
                    'positive_rate': 0.0,
                    'min_return': 0.0,
                    'max_return': 0.0,
                    'error': 'Script execution failed'
                })
            else:
                results.append(metrics)

                # Print brief result
                trades = metrics.get('successful_trades', 0)
                total = metrics.get('total_evaluated', 0)
                win_rate = (trades / total * 100) if total > 0 else 0.0
                avg_ret = metrics.get('avg_return', 0)
                print(f"Trades={trades:3d}/{total:<3d}, WinRate={win_rate:5.1f}%, AvgRet={avg_ret:6.2f}%")

        except Exception as e:
            print(f"ERROR: {e}")
            # Add a failed result
            results.append({
                'stop_loss_pct': sl,
                'take_profit_half_pct': tph,
                'take_profit_pct': tp,
                'successful_trades': 0,
                'total_evaluated': 0,
                'avg_return': 0.0,
                'positive_rate': 0.0,
                'min_return': 0.0,
                'max_return': 0.0,
                'error': str(e)
            })

    # Filter out results with errors and sort by average return (descending)
    valid_results = [r for r in results if 'error' not in r]
    valid_results.sort(key=lambda x: x.get('avg_return', -999), reverse=True)

    # Print summary
    print("\n" + "=" * 90)
    print("PARAMETER COMBINATIONS RESULTS (by average return):")
    print("=" * 90)
    print(f"{'Rank':<4} {'SL':<6} {'TP1':<6} {'TP2':<6} {'Trades':<8} {'Win%':<8} {'AvgRet':<10} {'MinRet':<8} {'MaxRet':<8}")
    print("-" * 90)
    for i, res in enumerate(valid_results, start=1):
        sl = res.get('stop_loss_pct', 0)
        tph = res.get('take_profit_half_pct', 0)
        tp = res.get('take_profit_pct', 0)
        trades = res.get('successful_trades', 0)
        total = res.get('total_evaluated', 0)
        win_rate = (trades / total * 100) if total > 0 else 0.0
        avg_ret = res.get('avg_return', 0)
        min_ret = res.get('min_return', 0)
        max_ret = res.get('max_return', 0)
        print(f"{i:<4} {sl:<6.1f} {tph:<6.1f} {tp:<6.1f} {trades:<8} {win_rate:<7.1f}% {avg_ret:<9.2f}% {min_ret:<7.2f}% {max_ret:<7.2f}%")

    # Save results to CSV
    output_dir = Path("/home/june/trading/reports")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "fujimoto_optimization_results_enhanced.csv"

    if valid_results:
        # Get all unique keys from all results
        fieldnames = set()
        for res in valid_results:
            fieldnames.update(res.keys())
        fieldnames = sorted(list(fieldnames))

        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(valid_results)

        print(f"\nResults saved to: {output_file}")

    print(f"\nOptimization complete! Tested {len(results)} combinations, {len(valid_results)} successful.")

if __name__ == "__main__":
    main()