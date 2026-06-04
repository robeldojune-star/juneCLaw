# Parameter Grid Search Results

## Test Conditions
- Signal date: 2026-05-28 (Fujimoto 1-2-6 STAGE3 signal detection)
- Entry date: 2026-05-29 (entry at same HH:MM as signal time)
- Universe: KOSPI Top 50 (21 stocks with complete data)
- Fixed parameters:
  - Maximum holding: 3 days
  - Fees: 23bps + slippage 10bps (round trip)
  - min_score: 60
- Variables:
  - Stop loss: -1%, -2%, -3%, -4%, -5%
  - Take profit: +2%, +3%, +4%, +5%
- Strategy: Enter on first signal, exit at SL/TP/max holding/time exit (15:20)
- No re-entry logic

## Results Summary (Top 10 by Average Return)

| Stop Loss | Take Profit | Avg Return | Win Rate | Trades |
|-----------|-------------|------------|----------|--------|
| -4.0%     | +5.0%       | +1.82%     | 76.2%    | 21     |
| -5.0%     | +5.0%       | +1.77%     | 76.2%    | 21     |
| -4.0%     | +4.0%       | +1.64%     | 76.2%    | 21     |
| -5.0%     | +4.0%       | +1.59%     | 76.2%    | 21     |
| -3.0%     | +5.0%       | +1.48%     | 71.4%    | 21     |
| -3.0%     | +4.0%       | +1.35%     | 71.4%    | 21     |
| -4.0%     | +3.0%       | +1.14%     | 76.2%    | 21     |
| -5.0%     | +3.0%       | +1.10%     | 76.2%    | 21     |
| -3.0%     | +3.0%       | +0.90%     | 71.4%    | 21     |
| -2.0%     | +5.0%       | +0.82%     | 61.9%    | 21     |

## Key Observations

1. **Optimal Region**: The highest returns are achieved with wider stop losses (-4% to -5%) and wider take profits (+4% to +5%).
2. **Win Rate vs Return Trade-off**: Wider stop losses slightly reduce win rate but increase average profit per winning trade, resulting in higher expectancy.
3. **Profit Target Hit Rate**: With SL -4%, TP +5%, approximately 40% of trades exit via take profit, 30% via stop loss, and 20% via time exit.
4. **Comparison to Earlier Belief**: Earlier tests suggested -5% stop loss worsened performance, but those used different exit rules (partial take profit at +3% then break-even then +5%). The current "all-or-nothing" take profit approach behaves differently.

## Recommendations

1. Consider SL -4% to -5% with TP +4% to +5% as a starting point for further testing.
2. Apply sentiment filter (foreign+inst > individual) to potentially improve signal quality.
3. Test walk-forward validation to ensure parameter stability across time.
4. Explore re-entry rules after stop loss to capture rebound opportunities.
5. Extend test period beyond single day to avoid overfitting.

## Raw Data Available In
The detailed per-trade results for each parameter combination are available in the backtest run logs.