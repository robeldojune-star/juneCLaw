# Indicator Formulas for RSI-CCI Trading Strategy

## Disparity Ratio
Disparity measures the percentage deviation of price from its moving average.

Formula:
```
Disparity = (Close / MA_n) × 100
```
Where:
- Close = current closing price
- MA_n = n-period simple moving average of close

In this strategy:
- n = 20
- Buy signal when Disparity ≤ 95 (price is 5% or more below MA20)

## Commodity Channel Index (CCI)
CCI identifies cyclical trends in commodities, equities, and currencies.

Formula:
```
Typical Price (TP) = (High + Low + Close) / 3
MA_TP = n-period SMA of TP
Mean Deviation = n-period average of |TP - MA_TP|
CCI = (TP - MA_TP) / (0.015 × Mean Deviation)
```
Where:
- The constant 0.015 ensures approximately 70-80% of values fall between -100 and +100

In this strategy:
- n = 20
- Buy signal when prior CCI ≤ -100 and current CCI > -100 (crossing upward through -100)

## Relative Strength Index (RSI)
RSI measures the magnitude of recent price changes to evaluate overbought/oversold conditions.

Formula:
```
RS = Average Gain / Average Loss
RSI = 100 - (100 / (1 + RS))
```
Where:
- Average Gain = average of upward price changes over n periods
- Average Loss = average of downward price changes over n periods (absolute value)

In this strategy:
- n = 14 (standard)
- Sell signal when prior RSI ≥ 70 and current RSI < 70 (crossing downward through 70)

## Volume Moving Average Filter
Ensures sufficient trading activity to validate signals.

Formula:
```
Volume MA = n-period SMA of Volume
```
Condition: Current Volume ≥ Volume MA

In this strategy:
- n = 20