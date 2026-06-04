import sys
sys.path.insert(0, '.')
from core.fujimoto_126_filter import PriceBar, simulate_fujimoto_126_trade
from datetime import datetime, timezone
print('Testing...')
bars = [
    PriceBar(ts=datetime(2026,5,28,9,0, tzinfo=timezone.utc), hhmm='09:00', open=100, high=100, low=99, close=99, volume=1000),
    PriceBar(ts=datetime(2026,5,28,9,1, tzinfo=timezone.utc), hhmm='09:01', open=99, high=101, low=99, close=100, volume=1000),
    PriceBar(ts=datetime(2026,5,28,9,2, tzinfo=timezone.utc), hhmm='09:02', open=100, high=101, low=97, close=98, volume=1000),
]
result = simulate_fujimoto_126_trade(bars, min_score=60.0)
print('Result:', result)