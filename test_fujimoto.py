import sys
sys.path.insert(0, '/home/june/trading')
from core.fujimoto_126_filter import evaluate_fujimoto_126, simulate_fujimoto_126_trade, PriceBar
from datetime import datetime, timezone

# Create a simple test: three bars where first bar high is 100, second bar high 101 (breakout), third bar high 102
# We'll just make dummy bars
bars = [
    PriceBar(ts=datetime(2026,5,28,9,0, tzinfo=timezone.utc), hhmm="09:00", open=100, high=100, low=99, close=99, volume=1000),
    PriceBar(ts=datetime(2026,5,28,9,1, tzinfo=timezone.utc), hhmm="09:01", open=99, high=101, low=99, close=100, volume=1000),
    PriceBar(ts=datetime(2026,5,28,9,2, tzinfo=timezone.utc), hhmm="09:02", open=100, high=102, low=100, close=101, volume=1000),
]
print("Testing evaluate_fujimoto_126 on three bars:")
result = evaluate_fujimoto_126(bars, min_score=60.0)
print(result)
print("\nTesting simulate_fujimoto_126_trade on same bars:")
sim = simulate_fujimoto_126_trade(bars, min_score=60.0, stop_loss_pct=-2.0, take_profit_pct=3.0, time_exit="15:20")
print(sim)