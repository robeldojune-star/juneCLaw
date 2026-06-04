# Backtest Summary: Top 10 KOSPI Stocks, 5 Days (2026-05-28 ~ 2026-06-01)

## Parameters
- Entry: disparity20 ≤ 100, CCI crosses -100 upward, volume ≥ 20‑period MA of volume
- Exit: Fixed profit target +1.5% (intraday)
- Lookback: 5 trading days (includes warm‑up day)
- Stocks: top 10 by market cap from kospi_top50_common_stocks_marketcap_naver.csv

## Results
| Stock | Trades | Win Rate | Avg Profit (%) | Individual Profits (%) |
|-------|--------|----------|----------------|------------------------|
| 005930 (삼성전자) | 1 | 100.0 | 1.61 | [1.61] |
| 000660 (SK하이닉스) | 2 | 100.0 | 1.58 | [1.52, 1.64] |
| 402340 (SK스퀘어) | 2 | 100.0 | 1.63 | [1.63, 1.64] |
| 005380 (현대차) | 3 | 100.0 | 1.62 | [1.62, 1.70, 1.55] |
| 009150 (삼성전기) | 5 | 100.0 | 1.87 | [1.91, 2.12, 1.73, 1.87, 1.72] |
| 373220 (LG에너지솔루션) | 3 | 100.0 | 1.63 | [1.57, 1.55, 1.76] |
| 035420 (네이버) | 2 | 100.0 | 1.66 | [1.57, 1.75] |
| 034020 (두산에너빌리티) | 1 | 100.0 | 1.55 | [1.55] |

**Overall**
- Total trades: 19
- Win rate: 100.0 %
- Average profit per trade: **1.68 %**
- Profit list: [1.61, 1.52, 1.64, 1.63, 1.64, 1.62, 1.70, 1.55, 1.91, 2.12, 1.73, 1.87, 1.72, 1.57, 1.55, 1.76, 1.57, 1.75, 1.55]

## Notes
- All trades reached the +1.5 % profit target intraday; no stop‑loss was triggered.
- The strategy uses absolute price values (Kiwoom returns signed strings) and fetches the previous calendar day for warm‑up of 20‑period moving averages.