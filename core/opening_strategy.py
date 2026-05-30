"""Opening multi-factor strategy primitives.

Pure, deterministic calculations only. Data collection and order execution stay
outside this module so Research AI/n8n can reuse the same scoring logic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Any, Iterable


@dataclass(frozen=True)
class OpeningBar:
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None = None


@dataclass(frozen=True)
class OpeningStrategyInput:
    stock_code: str
    today_open: float | None
    current_price: float | None
    yesterday_high: float | None
    yesterday_low: float | None
    bars: list[OpeningBar] = field(default_factory=list)
    financial_filter_passed: bool | None = None
    rsi: float | None = None
    turnover: float | None = None
    operating_income_positive: bool | None = None
    earnings_trend_ok: bool | None = None
    stage_entry_ready: bool | None = None


@dataclass(frozen=True)
class StrategyScore:
    strategy_id: str
    stock_code: str
    signal_type: str
    total_score: float
    score_details: dict[str, Any]
    blocking_conditions: list[str]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def opening_range(bars: Iterable[OpeningBar], window: int) -> dict[str, float | None]:
    selected = list(bars)[:window]
    highs = [b.high for b in selected if _num(b.high) is not None]
    lows = [b.low for b in selected if _num(b.low) is not None]
    closes = [b.close for b in selected if _num(b.close) is not None]
    volumes = [b.volume for b in selected if _num(b.volume) is not None]
    return {
        "window": window,
        "high": max(highs) if highs else None,
        "low": min(lows) if lows else None,
        "last_close": closes[-1] if closes else None,
        "volume_sum": sum(volumes) if volumes else None,
        "bar_count": len(selected),
    }


def volatility_score(inp: OpeningStrategyInput, *, k: float = 0.35, opening_window: int = 10) -> tuple[float, dict[str, Any], list[str]]:
    details: dict[str, Any] = {"max_score": 30, "k": k, "opening_window": opening_window}
    blocks: list[str] = []
    score = 0.0

    today_open = _num(inp.today_open)
    current = _num(inp.current_price)
    y_high = _num(inp.yesterday_high)
    y_low = _num(inp.yesterday_low)
    rng = opening_range(inp.bars, opening_window)

    entry_price = None
    if today_open is not None and y_high is not None and y_low is not None and y_high > y_low:
        entry_price = today_open + k * (y_high - y_low)
        if current is not None and current > entry_price:
            score += 10
    else:
        blocks.append("missing_volatility_breakout_inputs")

    open_gap_pct = None
    if today_open and current:
        open_gap_pct = (current - today_open) / today_open * 100
        if open_gap_pct > 0:
            score += 4
        if open_gap_pct >= 0.5:
            score += 4
    else:
        blocks.append("missing_open_gap_inputs")

    breakout = False
    if current is not None and rng["high"] is not None:
        breakout = current > float(rng["high"])
        if breakout:
            score += 7
    else:
        blocks.append("missing_opening_range_inputs")

    no_rebreak = False
    if breakout and rng["low"] is not None and current is not None:
        no_rebreak = current > float(rng["low"])
        if no_rebreak:
            score += 5

    details.update({
        "score": score,
        "entry_price": entry_price,
        "open_gap_pct": open_gap_pct,
        "opening_range": rng,
        "breakout": breakout,
        "no_rebreak": no_rebreak,
    })
    return min(score, 30.0), details, blocks


def flow_score(bars: list[OpeningBar]) -> tuple[float, dict[str, Any], list[str]]:
    details: dict[str, Any] = {"max_score": 30}
    blocks: list[str] = []
    if len(bars) < 3:
        return 0.0, {**details, "score": 0, "reason": "not_enough_bars"}, ["not_enough_bars_for_flow"]

    volumes = [b.volume for b in bars if _num(b.volume) is not None]
    closes = [b.close for b in bars if _num(b.close) is not None]
    score = 0.0

    volume_spike_ratio = None
    if len(volumes) >= 3 and mean(volumes[:-1]) > 0:
        volume_spike_ratio = volumes[-1] / mean(volumes[:-1])
        if volume_spike_ratio >= 1.10:
            score += 10
    else:
        blocks.append("missing_volume_series")

    price_up_with_volume = False
    if len(closes) >= 2 and len(volumes) >= 2:
        price_up = closes[-1] > closes[0]
        volume_up = volumes[-1] >= volumes[0]
        price_up_with_volume = price_up and volume_up
        if price_up_with_volume:
            score += 15
    else:
        blocks.append("missing_price_volume_series")

    high_break_with_volume = False
    highs = [b.high for b in bars if _num(b.high) is not None]
    if len(highs) >= 2 and closes:
        high_break_with_volume = closes[-1] >= max(highs[:-1])
        if high_break_with_volume and (volume_spike_ratio is None or volume_spike_ratio >= 1.0):
            score += 5

    details.update({
        "score": score,
        "volume_spike_ratio": volume_spike_ratio,
        "price_up_with_volume": price_up_with_volume,
        "high_break_with_volume": high_break_with_volume,
    })
    return min(score, 30.0), details, blocks


def pattern_score_placeholder(bars: list[OpeningBar]) -> tuple[float, dict[str, Any], list[str]]:
    """Temporary 90-day pattern placeholder.

    Real implementation must compare against 90 trading days of real Kiwoom data.
    For now, do not award points; report a clear block.
    """
    return 0.0, {"max_score": 25, "score": 0, "status": "requires_90d_intraday_backtest"}, ["pattern_model_not_ready"]


def risk_adjustment(inp: OpeningStrategyInput) -> tuple[float, dict[str, Any], list[str]]:
    details: dict[str, Any] = {"max_score": 15}
    blocks: list[str] = []
    score = 15.0
    if inp.financial_filter_passed is False:
        blocks.append("financial_filter_failed")
        score -= 10
    if inp.rsi is not None and inp.rsi >= 80:
        blocks.append("rsi_overheated")
        score -= 5
    details["score"] = max(score, 0.0)
    details["financial_filter_passed"] = inp.financial_filter_passed
    details["rsi"] = inp.rsi
    return max(score, 0.0), details, blocks


def fujimoto_aux_filter_score(inp: OpeningStrategyInput) -> tuple[float, dict[str, Any], list[str]]:
    details: dict[str, Any] = {
        "max_score": 15,
        "score": 0.0,
        "financial": {"score": 0.0, "operating_income_positive": inp.operating_income_positive, "earnings_trend_ok": inp.earnings_trend_ok, "source": "opendart"},
        "rsi": {"score": 0.0, "value": inp.rsi, "band": "unknown"},
        "liquidity": {"score": 0.0, "volume_spike_ratio": None, "turnover_ok": None},
        "stage_entry": {"score": 0.0, "stage_entry_ready": inp.stage_entry_ready, "mode": "1:2:6_risk_budget"},
    }
    blocks: list[str] = []
    score = 0.0

    # 1) financial (max 5)
    if inp.operating_income_positive is None and inp.earnings_trend_ok is None:
        blocks.append("fujimoto_financial_data_missing")
    elif inp.operating_income_positive is True and inp.earnings_trend_ok is True:
        details["financial"]["score"] = 5.0
        score += 5.0
    elif inp.operating_income_positive is True:
        details["financial"]["score"] = 3.0
        score += 3.0
    else:
        blocks.append("fujimoto_financial_filter_failed")

    # 2) rsi (max 4)
    rsi = inp.rsi
    if rsi is None:
        blocks.append("fujimoto_rsi_missing")
    elif rsi >= 80:
        details["rsi"]["band"] = "overheated"
        blocks.append("fujimoto_rsi_overheated")
    elif 45 <= rsi < 70:
        details["rsi"]["score"] = 4.0
        details["rsi"]["band"] = "trend"
        score += 4.0
    elif 30 <= rsi < 45:
        details["rsi"]["score"] = 2.0
        details["rsi"]["band"] = "rebound"
        score += 2.0
    else:
        details["rsi"]["band"] = "neutral"

    # 3) liquidity (max 3)
    volumes = [v for b in inp.bars if (v := _num(b.volume)) is not None]
    volume_spike_ratio = None
    if len(volumes) >= 3 and mean(volumes[:-1]) > 0:
        volume_spike_ratio = volumes[-1] / float(mean(volumes[:-1]))
    details["liquidity"]["volume_spike_ratio"] = volume_spike_ratio

    turnover_ok = inp.turnover is not None and inp.turnover > 0
    details["liquidity"]["turnover_ok"] = turnover_ok
    if volume_spike_ratio is None:
        blocks.append("fujimoto_volume_insufficient")
    elif volume_spike_ratio >= 1.30 and turnover_ok:
        details["liquidity"]["score"] = 3.0
        score += 3.0
    elif volume_spike_ratio >= 1.10:
        details["liquidity"]["score"] = 2.0
        score += 2.0
    else:
        blocks.append("fujimoto_volume_insufficient")

    if not turnover_ok:
        blocks.append("fujimoto_turnover_insufficient")

    # 4) staged entry readiness (max 3)
    if inp.stage_entry_ready is None:
        blocks.append("fujimoto_stage_entry_not_ready")
    elif inp.stage_entry_ready is True:
        details["stage_entry"]["score"] = 3.0
        score += 3.0

    details["score"] = min(score, 15.0)
    return min(score, 15.0), details, blocks


def score_opening_multi_factor(inp: OpeningStrategyInput) -> StrategyScore:
    v_score, v_details, v_blocks = volatility_score(inp)
    f_score, f_details, f_blocks = flow_score(inp.bars)
    p_score, p_details, p_blocks = pattern_score_placeholder(inp.bars)
    r_score, r_details, r_blocks = risk_adjustment(inp)
    fa_score, fa_details, fa_blocks = fujimoto_aux_filter_score(inp)
    total = v_score + f_score + p_score + r_score
    blocks = v_blocks + f_blocks + p_blocks + r_blocks + fa_blocks

    critical_blocks = {
        "financial_filter_failed",
        "fujimoto_financial_filter_failed",
        "fujimoto_rsi_overheated",
        "fujimoto_gap_overheated",
    }

    if any(b in critical_blocks for b in blocks):
        signal = "HOLD"
    elif total >= 70 and fa_score >= 8:
        signal = "BUY"
    elif total >= 55:
        signal = "WATCH"
    else:
        signal = "HOLD"

    return StrategyScore(
        strategy_id="opening_multi_factor_v1",
        stock_code=inp.stock_code,
        signal_type=signal,
        total_score=round(total, 4),
        score_details={
            "volatility": v_details,
            "flow": f_details,
            "pattern": p_details,
            "risk_adjustment": r_details,
            "fujimoto_aux_filter": fa_details,
            "thresholds": {
                "buy_candidate": 70,
                "watch_min": 55,
                "fujimoto_aux_min": 8,
                "note": "candidate thresholds pending backtest",
            },
        },
        blocking_conditions=blocks,
        reason="opening multi-factor candidate score with fujimoto auxiliary filter; 90d pattern currently placeholder until real-data backtest is available",
    )
