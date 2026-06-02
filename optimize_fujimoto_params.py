#!/usr/bin/env python3
"""
Parameter optimization runner for Fujimoto 1-2-6 strategy.
Runs the existing backtest logic with different parameter combinations.
"""
import sys
import itertools
import subprocess
import tempfile
import os
import csv
from pathlib import Path

def run_backtest_with_params(stop_loss_pct, take_profit_half_pct, take_profit_pct):
    """Run backtest by creating a temporary modified script."""
    # Read the original script
    script_path = Path("/home/june/trading/backtest_fujimoto_custom_swing_no_time_exit.py")
    with open(script_path, 'r') as f:
        content = f.read()
    
    # Replace the hardcoded parameters in the simulate_custom_swing function call
    # Find the line that calls simulate_custom_swing and replace its parameters
    import re
    
    # Pattern to find the simulate_custom_swing call with default parameters
    pattern = r'simulate_custom_swing\(bars, \*[^)]*stop_loss_pct=-1\.0, take_profit_pct=3\.0, take_profit_half_pct=5\.0[^)]*\)'
    
    # Replacement string
    replacement = f'simulate_custom_swing(bars, stop_loss_pct={stop_loss_pct}, take_profit_pct={take_profit_pct}, take_profit_half_pct={take_profit_half_pct}, max_holding_days=3, fee_bps=23.0, slippage_bps=10.0, min_score=60.0)'
    
    # Apply the replacement
    modified_content = re.sub(pattern, replacement, content)
    
    # Also need to handle the case where it might be called differently
    # Let's also replace any other instances of the hardcoded values in function definitions
    # Replace the default parameter values in the function signature
    modified_content = modified_content.replace(
        'def simulate_custom_swing(bars, *, stop_loss_pct=-1.0, take_profit_pct=3.0, take_profit_half_pct=5.0, max_holding_days=3, fee_bps=23.0, slippage_bps=10.0, min_score=60.0):',
        f'def simulate_custom_swing(bars, *, stop_loss_pct={stop_loss_pct}, take_profit_pct={take_profit_pct}, take_profit_half_pct={take_profit_half_pct}, max_holding_days=3, fee_bps=23.0, slippage_bps=10.0, min_score=60.0):'
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
            timeout=120  # Increased timeout for backtest
        )
        
        # Check if script ran successfully
        if result.returncode != 0:
            print(f"Script failed with return code {result.returncode}")
            print(f"Stderr: {result.stderr}")
            return None
        
        # Parse output to extract results
        # The script prints a summary at the end
        output = result.stdout
        
        # Extract key metrics from output
        metrics = {}
        for line in output.split('\n'):
            line = line.strip()
            if 'Total trades:' in line:
                try:
                    metrics['total_trades'] = int(line.split(':')[1].strip())
                except:
                    pass
            elif 'Win rate:' in line:
                try:
                    win_rate_str = line.split(':')[1].strip().replace('%', '')
                    metrics['win_rate'] = float(win_rate_str) / 100.0
                except:
                    pass
            elif 'Average return:' in line:
                try:
                    avg_return_str = line.split(':')[1].strip().replace('%', '')
                    metrics['avg_return'] = float(avg_return_str)
                except:
                    pass
            elif 'Max return:' in line:
                try:
                    max_return_str = line.split(':')[1].strip().replace('%', '')
                    metrics['max_return'] = float(max_return_str)
                except:
                    pass
            elif 'Max loss:' in line:
                try:
                    max_loss_str = line.split(':')[1].strip().replace('%', '')
                    metrics['max_loss'] = float(max_loss_str)
                except:
                    pass
            elif 'Profit factor:' in line:
                try:
                    profit_factor_str = line.split(':')[1].strip()
                    metrics['profit_factor'] = float(profit_factor_str)
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
    """Run parameter optimization."""
    # Define parameter ranges
    stop_loss_values = [-0.5, -1.0, -1.5]  # as percent (negative)
    take_profit_half_values = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]  # first target (sell 50%)
    take_profit_values = [4.0, 5.0, 6.0, 7.0, 8.0]   # second target (sell remaining 50%)
    
    print("Starting Fujimoto 1-2-6 strategy parameter optimization...")
    print(f"Testing {len(stop_loss_values)} stop loss values: {stop_loss_values}")
    print(f"Testing {len(take_profit_half_values)} take profit half values: {take_profit_half_values}")
    print(f"Testing {len(take_profit_values)} take profit values: {take_profit_values}")
    print(f"Total combinations: {len(stop_loss_values) * len(take_profit_half_values) * len(take_profit_values)}")
    print("=" * 60)
    
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
                    'total_trades': 0,
                    'win_rate': 0.0,
                    'avg_return': 0.0,
                    'max_return': 0.0,
                    'max_loss': 0.0,
                    'profit_factor': 0.0,
                    'error': 'Script execution failed'
                })
            else:
                results.append(metrics)
                
                # Print brief result
                trades = metrics.get('total_trades', 0)
                win_rate = metrics.get('win_rate', 0)
                avg_ret = metrics.get('avg_return', 0)
                print(f"Trades={trades:3d}, WinRate={win_rate:5.1%}, AvgRet={avg_ret:6.2f}%")
                
        except Exception as e:
            print(f"ERROR: {e}")
            # Add a failed result
            results.append({
                'stop_loss_pct': sl,
                'take_profit_half_pct': tph,
                'take_profit_pct': tp,
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_return': 0.0,
                'max_return': 0.0,
                'max_loss': 0.0,
                'profit_factor': 0.0,
                'error': str(e)
            })
    
    # Filter out results with errors and sort by average return (descending)
    valid_results = [r for r in results if 'error' not in r]
    valid_results.sort(key=lambda x: x.get('avg_return', -999), reverse=True)
    
    # Print summary
    print("\n" + "=" * 80)
    print("TOP 10 PARAMETER COMBINATIONS (by average return):")
    print("=" * 80)
    print(f"{'Rank':<4} {'SL':<6} {'TP1':<6} {'TP2':<6} {'Trades':<8} {'Win%':<8} {'AvgRet':<10} {'MaxRet':<8} {'MaxLoss':<8} {'PF':<8}")
    print("-" * 80)
    for i, res in enumerate(valid_results[:10], start=1):
        sl = res.get('stop_loss_pct', 0)
        tph = res.get('take_profit_half_pct', 0)
        tp = res.get('take_profit_pct', 0)
        trades = res.get('total_trades', 0)
        win_rate = res.get('win_rate', 0)
        avg_ret = res.get('avg_return', 0)
        max_ret = res.get('max_return', 0)
        max_loss = res.get('max_loss', 0)
        pf = res.get('profit_factor', 0)
        print(f"{i:<4} {sl:<6.1f} {tph:<6.1f} {tp:<6.1f} {trades:<8} {win_rate:<7.1%} {avg_ret:<9.2f}% {max_ret:<7.2f}% {max_loss:<7.2f}% {pf:<7.2f}")
    
    # Save results to CSV
    output_dir = Path("/home/june/trading/reports")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "fujimoto_optimization_results.csv"
    
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
        
        print(f"\nFull results saved to: {output_file}")
    
    print(f"\nOptimization complete! Tested {len(results)} combinations, {len(valid_results)} successful.")

if __name__ == "__main__":
    main()