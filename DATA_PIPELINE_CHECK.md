# Data Pipeline Check: OpenDART Disclosures vs. Daily Price Data

## Summary

We successfully collected OpenDART disclosures for three KOSPI‑top‑50 stocks:
- **004410** (서울식품): 33 disclosures (2025‑12‑11 → 2026‑05‑28)
- **008700** (아남전자): 18 disclosures (2025‑12‑16 → 2026‑05‑29)
- **015260** (에이엔피): 23 disclosures (2025‑12‑24 → 2026‑05‑15)

However, the `daily_prices` table currently contains OHLCV data for only four stocks:
- **005930** (삼성전자): 1 row (2023‑12‑06)
- **009540** (KODEX 코스닥150레버리지): 403 rows (2023‑12‑13 → 2025‑08‑11)
- **034730** (TIGER 차이나지수선물레버리지): 10 rows (2023‑12‑06 → 2026‑03‑26)
- **086790** (KODEX 코스피100레버리지): 586 rows (2023‑12‑28 → 2026‑05‑29)

There is **zero overlap** between the stocks that have disclosures and the stocks that have daily price data. Consequently, we cannot compute a correlation between disclosure frequency and volume spikes at this time.

## Root Cause

The daily price data collection script (`scripts/collect_daily_prices_kiwoom.py`) appears to have been run only for a subset of stocks (likely for testing or a specific universe). The disclosure collection script we just ran targeted the active KOSPI‑top‑50 list, but the price table does not yet reflect that same universe.

## Recommended Next Steps

1. **Populate daily_prices for all active KOSPI‑top‑50 stocks**  
   Run the existing collection script (or a variant) to fetch daily OHLCV for every active stock in `kospi_top50` where `is_active = True`.  
   Example command:
   ```bash
   cd /home/june/trading
   source .env
   python3 scripts/collect_daily_prices_kiwoom.py
   ```
   (If the script requires arguments, adjust accordingly; it may already loop over the active list.)

2. **Verify the overlap**  
   After the collection, re‑run the coverage check:
   ```bash
   python3 scripts/check_data_coverage.py
   ```
   You should see that the disclosure stocks now also appear in the daily prices list.

3. **Run the correlation analysis**  
   With overlapping data, the correlation script (`scripts/analyze_volume_disclosure_correlation.py`) will then produce meaningful Pearson and Spearman coefficients between disclosure counts and daily volume percent changes.

4. **Consider intraday data for bid/ask‑based signals**  
   As previously noted, the intraday table still lacks bid/ask fields. To enable the enhanced bid/ask pressure and slippage filters in your backtest, you will need to update the intraday collection script (`collect_intraday_90d.py`) to parse and store the bid/ask values from the Kiwoom `ka10080` response.

## Immediate Actionable Items (if you want to proceed now)

- I can run the daily price collection script for you (it may take a few minutes due to API rate limits).  
- After that, we can immediately re‑run the correlation analysis and share the results.

Please let me know if you’d like me to execute the daily price collection, or if you have any other preferences (e.g., focusing on a different set of stocks, adjusting the correlation metrics, etc.).

---

*Note: All API keys remain stored only in `/home/june/trading/.env` and are not logged or shared.*