import sys
sys.path.insert(0, '/home/june/trading')
from core.fujimoto_126_filter import PriceBar, simulate_fujimoto_126_trade
from datetime import datetime, timezone

# Test case 1: Stop loss hit
print("Test 1: Stop loss hit")
bars = [
    PriceBar(ts=datetime(2026,5,28,9,0, tzinfo=timezone.utc), hhmm="09:00", open=100, high=100, low=99, close=99, volume=1000),
    PriceBar(ts=datetime(2026,5,28,9,1, tzinfo=timezone.utc), hhmm="09:01", open=99, high=101, low=99, close=100, volume=1000),  # breakout
    PriceBar(ts=datetime(2026,5,28,9,2, tzinfo=timezone.utc), hhmm="09:02", open=100, high=101, low=97, close=98, volume=1000),  # low hits stop loss (98 <= 100 * 0.98 = 98)
]
result = simulate_fujimoto_126_trade(bars, min_score=60.0)
print("Result:", result)
print()

# Test case 2: Take profit hit (first half) then time exit
print("Test 2: Take profit then time exit")
bars = [
    PriceBar(ts=datetime(2026,5,28,9,0, tzinfo=timezone.utc), hhmm="09:00", open=100, high=100, low=99, close=99, volume=1000),
    PriceBar(ts=datetime(2026,5,28,9,1, tzinfo=timezone.utc), hhmm="09:01", open=99, high=101, low=99, close=100, volume=1000),  # breakout
    PriceBar(ts=datetime(2026,5,28,9,2, tzinfo=timezone.utc), hhmm="09:02", open=100, high=104, low=100, close=103, volume=1000),  # high hits take profit (103 >= 100 * 1.03 = 103)
    PriceBar(ts=datetime(2026,5,28,9,3, tzinfo=timezone.utc), hhmm="09:03", open=103, high=103, low=102, close=102, volume=1000),
    PriceBar(ts=datetime(2026,5,28,9,4, tzinfo=timezone.utc), hhmm="09:04", open=102, high=102, low=101, close=101, volume=1000),
    # ... until time exit
]
# Make it simple: just a few bars and assume time exit is late
result = simulate_fujimoto_126_trade(bars, min_score=60.0, time_exit="15:20")
print("Result:", result)
print()

# Test case 3: Normal exit at last close
print("Test 3: Normal exit at last close")
bars = [
    PriceBar(ts=datetime(2026,5,28,9,0, tzinfo=timezone.utc), hhmm="09:00", open=100, high=100, low=99, close=99, volume=1000),
    PriceBar(ts=datetime(2026,5,28,9,1, tzinfo=timezone.utc), hhmm="09:01", open=99, high=101, low=99, close=100, volume=1000),  # breakout
    PriceBar(ts=datetime(2026,5,28,9,2, tzinfo=timezone.utc), hhmm="09:02", open=100, high=102, low=100, close=101, volume=1000),
    PriceBar(ts=datetime(2026,5,28,9,3, tzinfo=timezone.utc), hhmm="09:03", open=101, high=101, low=100, close=100, volume=1000),
]
result = simulate_fujimoto_126_trade(bars, min_score=60.0)
print("Result:", result)