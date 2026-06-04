# 5‑Day Backtest Summary (2026‑05‑28 ~ 2026‑06‑01)

**Strategy**: disparity20 ≤ 100, CCI crosses ‑100 upward, volume ≥ volume MA20  
**Exit**: Intraday profit target +1.5% (fixed)  

## Results
- Total buy signals: 8
- Signals achieving ≥1.5% profit later same day: 4 (50%)
- Average max profit per signal: +1.46%
- Median max profit: +1.57%
- Best case profit: +2.79%

## Details (top 5 by max profit)
| Date       | Entry Time | Entry Price | Exit Time (max profit) | Max Profit | Exit Price |
|------------|------------|-------------|------------------------|------------|------------|
| 20260528   | 12:40:00   | 121,700     | 15:14:00               | +2.79%     | 125,100    |
| 20260529   | 10:36:00   | 120,400     | 15:30:00               | +2.41%     | 123,300    |
| 20260529   | 11:25:00   | 120,500     | 15:30:00               | +2.32%     | 123,300    |
| 20260529   | 12:19:00   | 121,000     | 15:30:00               | +1.90%     | 123,300    |
| 20260529   | 09:58:00   | 121,800     | 15:30:00               | +1.23%     | 123,300    |

## Notes
- The strategy uses 20‑period moving averages; prior day data is fetched for warm‑up.
- Price strings from Kiwoom are converted to absolute values to avoid sign issues.
- No stop‑loss is implemented in this version; consider adding one (e.g., ‑1 % or ‑5 %) for live trading.
