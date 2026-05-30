from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.fujimoto_126_filter import PriceBar, evaluate_fujimoto_126, simulate_fujimoto_126_trade


def b(hhmm: str, open_=100.0, high=100.0, low=100.0, close=100.0, volume=1000):
    hour, minute = map(int, hhmm.split(":"))
    return PriceBar(
        ts=datetime(2026, 5, 29, hour, minute, tzinfo=timezone.utc),
        hhmm=hhmm,
        open=float(open_),
        high=float(high),
        low=float(low),
        close=float(close),
        volume=int(volume),
    )


def trend_setup_bars():
    bars = []
    price = 100.0
    # Long enough warm-up for MACD and Ichimoku. First part sells down, then recovers strongly.
    for i in range(70):
        hhmm = f"09:{i:02d}" if i < 60 else f"10:{i-60:02d}"
        if i < 28:
            price -= 0.55
        elif i < 40:
            price += 0.15
        else:
            price += 0.95
        bars.append(b(hhmm, open_=price - 0.15, high=price + 0.35, low=price - 0.45, close=price, volume=1000 + i * 20))
    return bars


def test_evaluate_fujimoto_126_identifies_full_stage3_trend_confirmation():
    result = evaluate_fujimoto_126(trend_setup_bars())

    assert result["strategy"] == "fujimoto_126_trend_confirmation_v1"
    assert result["position_stage"] == "STAGE3"
    assert result["signal"] == "HIGH_CONFIDENCE_CANDIDATE"
    assert result["score_total"] >= 60
    assert result["score_details"]["rsi_recovery"]["score"] > 0
    assert result["score_details"]["macd_confirmation"]["score"] > 0
    assert result["score_details"]["ichimoku_confirmation"]["score"] > 0
    assert "paper_order_blocked" in result["blocking_conditions"]
    assert "real_order_blocked" in result["blocking_conditions"]


def test_evaluate_fujimoto_126_blocks_when_ichimoku_has_insufficient_bars():
    bars = [b(f"09:{i:02d}", close=100 + i * 0.1, high=100 + i * 0.1, low=99 + i * 0.1) for i in range(20)]

    result = evaluate_fujimoto_126(bars)

    assert result["signal"] == "BLOCKED"
    assert result["position_stage"] in {"NONE", "STAGE1", "STAGE2"}
    assert "insufficient_intraday_bars_for_ichimoku" in result["blocking_conditions"]
    assert result["paper_order_allowed"] is False
    assert result["real_order_allowed"] is False


def test_simulate_fujimoto_126_trade_uses_staged_entry_and_exit_without_orders():
    bars = trend_setup_bars()
    # Add a late reversal so staged exits can trigger before time exit.
    price = bars[-1].close
    for i in range(25):
        price -= 1.25
        hhmm = f"10:{10+i:02d}"
        bars.append(b(hhmm, open_=price + 0.2, high=price + 0.3, low=price - 0.7, close=price, volume=2500))

    trade = simulate_fujimoto_126_trade(bars, fee_bps=0, slippage_bps=0)

    assert trade["ok"] is True
    assert trade["entry_time"] is not None
    assert trade["exit_time"] is not None
    assert trade["entry_stage"] == "STAGE3"
    assert trade["position_units"] == 9
    assert trade["order_execution_enabled"] is False
    assert trade["paper_order_allowed"] is False
    assert trade["real_order_allowed"] is False
    assert trade["net_return_pct"] is not None
