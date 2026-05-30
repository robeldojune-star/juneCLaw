from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.backtest_entry_variant_comparison import Bar, simulate_entry_variant


def b(hhmm, open_=100, high=100, low=100, close=100, volume=100):
    hour, minute = map(int, hhmm.split(":"))
    return Bar(
        ts=datetime(2026, 5, 29, hour, minute, tzinfo=timezone.utc),
        hhmm=hhmm,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def base_or10_bars(extra):
    rows = [b(f"09:{m:02d}", high=100, low=95, close=99, volume=100) for m in range(0, 11)]
    return rows + extra


def test_immediate_breakout_enters_first_bar_after_range_breaks_high():
    bars = base_or10_bars([b("09:11", high=101, low=99, close=100.5, volume=100)])

    result = simulate_entry_variant(bars, variant="immediate_breakout", window_minutes=10)

    assert result["ok"] is True
    assert result["entry_time"] == "09:11"
    assert result["entry_price"] == 100.5


def test_entry_window_blocks_late_breakout_after_10am():
    bars = base_or10_bars([b("10:01", high=101, low=99, close=100.5, volume=100)])

    result = simulate_entry_variant(bars, variant="entry_window", window_minutes=10, entry_end="10:00")

    assert result["ok"] is False
    assert "no_breakout_inside_entry_window" in result["blocking_conditions"]


def test_volume_confirmed_breakout_requires_volume_multiple():
    bars = base_or10_bars([b("09:11", high=101, low=99, close=100.5, volume=120)])

    result = simulate_entry_variant(bars, variant="volume_confirmed_breakout", window_minutes=10, volume_multiplier=1.5)

    assert result["ok"] is False
    assert "breakout_volume_below_threshold" in result["blocking_conditions"]


def test_early_drop_filter_rejects_breakout_with_fast_adverse_move():
    bars = base_or10_bars([
        b("09:11", high=101, low=100, close=100.5, volume=200),
        b("09:12", high=100.6, low=99.8, close=100.0, volume=150),
        b("09:13", high=100.2, low=99.0, close=99.2, volume=150),
    ])

    result = simulate_entry_variant(
        bars,
        variant="early_drop_filtered_breakout",
        window_minutes=10,
        early_drop_minutes=3,
        early_drop_pct=-1.0,
    )

    assert result["ok"] is False
    assert "early_drop_filter_triggered" in result["blocking_conditions"]


def test_pullback_rebreak_waits_for_pullback_then_rebreak():
    bars = base_or10_bars([
        b("09:11", high=101, low=100.2, close=100.8, volume=200),
        b("09:12", high=100.4, low=99.8, close=100.0, volume=120),
        b("09:13", high=101.2, low=100.1, close=101.0, volume=180),
    ])

    result = simulate_entry_variant(bars, variant="pullback_rebreak", window_minutes=10)

    assert result["ok"] is True
    assert result["entry_time"] == "09:13"
    assert result["entry_price"] == 101.0


def test_ten_oclock_confirmation_enters_at_10_if_close_above_range_high():
    bars = base_or10_bars([
        b("09:11", high=101, low=99, close=100.5, volume=100),
        b("10:00", high=102, low=100, close=101.5, volume=200),
    ])

    result = simulate_entry_variant(bars, variant="ten_oclock_confirmation", window_minutes=10)

    assert result["ok"] is True
    assert result["entry_time"] == "10:00"
    assert result["entry_price"] == 101.5
