#!/usr/bin/env python3
"""
Analyze correlation between OpenDART disclosures and trading volume spikes.
"""

import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
import math

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

from core.supabase_rest import SupabaseRestClient

def rank_data(data):
    """
    Assign ranks to data, with average rank for ties.
    Returns a list of ranks in the same order as data.
    """
    n = len(data)
    # Create list of (value, index)
    indexed = [(data[i], i) for i in range(n)]
    # Sort by value
    indexed.sort(key=lambda x: x[0])
    
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        # Find all indices with the same value
        while j < n and indexed[j][0] == indexed[i][0]:
            j += 1
        # The rank for this group is the average of the positions they would have gotten (1-indexed)
        # Positions from i+1 to j (inclusive) in the sorted list.
        avg_rank = (i + 1 + j) / 2.0  # because positions are 1-indexed: i+1, i+2, ..., j
        for k in range(i, j):
            original_index = indexed[k][1]
            ranks[original_index] = avg_rank
        i = j
    return ranks

def main():
    sb = SupabaseRestClient()
    
    print("Fetching disclosures...")
    disclosures = sb.get('dart_disclosures')
    print(f"Fetched {len(disclosures)} disclosure rows.")
    
    # Aggregate disclosures by stock_code and date (rcept_dt)
    disclosure_counts = defaultdict(int)  # (stock_code, date) -> count
    for d in disclosures:
        stock = d['stock_code']
        date_str = d['rcept_dt']  # already in YYYY-MM-DD format from the table
        disclosure_counts[(stock, date_str)] += 1
    
    print(f"Disclosure counts for {len(disclosure_counts)} (stock, date) pairs.")
    
    # Get the set of stock codes we care about (from disclosures)
    stock_codes = set(stock for stock, _ in disclosure_counts.keys())
    print(f"Stocks with disclosures: {sorted(stock_codes)}")
    
    # Fetch daily prices for each stock individually
    prices_by_stock = defaultdict(dict)  # stock_code -> {date: {volume, ...}}
    for stock in stock_codes:
        print(f"Fetching daily prices for {stock}...")
        rows = sb.get('daily_prices', params={'stock_code': f'eq.{stock}'})
        print(f"  Fetched {len(rows)} rows.")
        for p in rows:
            date_str = p['date']  # YYYY-MM-DD
            prices_by_stock[stock][date_str] = p
    
    total_rows = sum(len(v) for v in prices_by_stock.values())
    print(f"Total daily price rows for disclosure stocks: {total_rows}")
    
    # Compute volume spike metric: we'll use the percentage change from previous day.
    # For each stock, we need to sort dates and compute (volume_t - volume_{t-1}) / volume_{t-1}
    volume_spikes = defaultdict(dict)  # stock_code -> {date: volume_change_pct}
    for stock, date_dict in prices_by_stock.items():
        # Sort dates
        sorted_dates = sorted(date_dict.keys())
        prev_volume = None
        for date in sorted_dates:
            volume = date_dict[date]['volume']
            if prev_volume is not None and prev_volume != 0:
                change = (volume - prev_volume) / prev_volume
                volume_spikes[stock][date] = change
            else:
                volume_spikes[stock][date] = None  # No previous day or zero volume
            prev_volume = volume
    
    # Now join disclosure counts and volume spikes
    # We'll create a list of (disclosure_count, volume_change_pct) for each (stock, date) where both exist.
    paired_data = []
    for (stock, date), count in disclosure_counts.items():
        if stock in volume_spikes and date in volume_spikes[stock]:
            change = volume_spikes[stock][date]
            if change is not None:
                paired_data.append((count, change))
    
    print(f"Paired data points: {len(paired_data)}")
    
    if len(paired_data) < 2:
        print("Not enough data to compute correlation.")
        return
    
    # Compute Pearson correlation
    # Pearson r = cov(X,Y) / (std_X * std_Y)
    n = len(paired_data)
    sum_x = sum(x for x, _ in paired_data)
    sum_y = sum(y for _, y in paired_data)
    sum_xy = sum(x * y for x, y in paired_data)
    sum_x2 = sum(x * x for x, _ in paired_data)
    sum_y2 = sum(y * y for _, y in paired_data)
    
    numerator = n * sum_xy - sum_x * sum_y
    denominator = math.sqrt((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y))
    
    if denominator == 0:
        print("Cannot compute correlation (zero variance).")
        return
    
    pearson_r = numerator / denominator
    
    print(f"Pearson correlation between disclosure count and volume % change: {pearson_r:.4f}")
    
    # Also compute Spearman correlation (rank-based) for robustness
    disclosure_counts_list = [x for x, _ in paired_data]
    volume_changes_list = [y for _, y in paired_data]
    
    # Rank the data
    ranks_x = rank_data(disclosure_counts_list)
    ranks_y = rank_data(volume_changes_list)
    
    # Now compute Pearson on the ranks
    sum_rx = sum(ranks_x)
    sum_ry = sum(ranks_y)
    sum_rxy = sum(rx * ry for rx, ry in zip(ranks_x, ranks_y))
    sum_rx2 = sum(rx * rx for rx in ranks_x)
    sum_ry2 = sum(ry * ry for ry in ranks_y)
    
    numerator_r = n * sum_rxy - sum_rx * sum_ry
    denominator_r = math.sqrt((n * sum_rx2 - sum_rx * sum_rx) * (n * sum_ry2 - sum_ry * sum_ry))
    
    if denominator_r == 0:
        spearman_rho = 0
    else:
        spearman_rho = numerator_r / denominator_r
    
    print(f"Spearman correlation between disclosure count and volume % change: {spearman_rho:.4f}")
    
    # Show some examples
    print("\nTop 5 disclosure days by volume % change:")
    sorted_by_change = sorted(paired_data, key=lambda pair: abs(pair[1]), reverse=True)
    for count, change in sorted_by_change[:5]:
        print(f"  Disclosures: {count:2d}, Volume change: {change*100:6.2f}%")
    
    print("\nTop 5 disclosure days by disclosure count:")
    sorted_by_count = sorted(paired_data, key=lambda pair: pair[0], reverse=True)
    for count, change in sorted_by_count[:5]:
        print(f"  Disclosures: {count:2d}, Volume change: {change*100:6.2f}%")

if __name__ == '__main__':
    main()