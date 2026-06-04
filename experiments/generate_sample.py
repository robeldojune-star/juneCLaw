#!/usr/bin/env python3
import pandas as pd
import numpy as np

# Generate synthetic 1-minute data for a day (09:00-15:30) = 390 minutes
# We'll create a pattern: price drops sharply then rises sharply
time_idx = pd.date_range(start='2026-06-01 09:00:00', end='2026-06-01 15:30:00', freq='1min')
n = len(time_idx)
# Base price
base = 120000
# Create a drop then rise
# First 60 minutes: gradual drop to trigger oversold
drop = np.linspace(0, -3000, 60)  # drop 3000 points
# Next 60 minutes: sharp rise to trigger overbought
rise = np.linspace(0, 5000, 60)   # rise 5000 points
# Rest: sideways
side = np.zeros(n - 120)
price_change = np.concatenate([drop, rise, side])
# Add some noise
price = base + price_change + np.random.normal(0, 100, n)
# Ensure positive
price = np.maximum(price, 100000)
# Generate OHLC from price with some spread
open_price = price + np.random.normal(0, 50, n)
high_price = price + np.abs(np.random.normal(0, 150, n))
low_price = price - np.abs(np.random.normal(0, 150, n))
close_price = price
volume = np.random.randint(100, 1000, n)

df = pd.DataFrame({
    'time': time_idx,
    'open': open_price,
    'high': high_price,
    'low': low_price,
    'close': close_price,
    'volume': volume
})
# Save to CSV
df.to_csv('/home/june/trading/data/intraday/042660_20260601_sample.csv', index=False)
print(f'Generated sample CSV with {n} rows')
print(f'First few rows:\\n{df.head()}')
print(f'Last few rows:\\n{df.tail()}')