"""Fujimoto/Shigeru 1-2-6 auxiliary trend-confirmation filter.

Pure read-only calculations for backtests and research reports.  This module
never places orders and deliberately returns explicit paper/real order blocks.

Strategy interpretation from the report:
- RSI recovery: oversold/rebound or intraday trend band recovery.
- MACD confirmation: bullish crossover or positive histogram/momentum.
- Ichimoku confirmation: price above cloud, optionally after prior cloud touch.
- Position staging: 1/9 -> 2/9 -> 6/9 risk-budget units.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from statistics import mean
from typing import Any, Iterable


STRATEGY_ID = "fujimoto_126_trend_confirmation_v1"
ORDER_BLOCKS = ["paper_order_blocked", "real_order_blocked"]


@dataclass(frozen=True)
class PriceBar:
    ts: datetime
    hhmm: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_volume: int = 0
    ask_volume: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def _ema(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    out: list[float | None] = []
    alpha = 2.0 / (period + 1.0)
    ema_value: float | None = None
    for idx, value in enumerate(values):
        if idx + 1 < period:
            out.append(None)
            continue
        if idx + 1 == period:
            ema_value = mean(values[:period])
        else:
            assert ema_value is not None
            ema_value = value * alpha + ema_value * (1.0 - alpha)
        out.append(ema_value)
    return out


def rsi_series(closes: Iterable[float], period: int = 14) -> list[float | None]:
    values = list(closes)
    if len(values) < period + 1:
        return [None] * len(values)
    out: list[float | None] = [None] * len(values)
    gains: list[float] = []
    losses: list[float] = []
    for idx in range(1, period + 1):
        delta = values[idx] - values[idx - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    out[period] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    for idx in range(period + 1, len(values)):
        delta = values[idx] - values[idx - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[idx] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    return out


def macd_series(closes: Iterable[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, list[float | None]]:
    values = list(closes)
    fast_ema = _ema(values, fast)
    slow_ema = _ema(values, slow)
    macd_line: list[float | None] = []
    for f, s in zip(fast_ema, slow_ema):
        macd_line.append(None if f is None or s is None else f - s)

    # EMA for MACD line over valid values while preserving alignment.
    valid = [v for v in macd_line if v is not None]
    valid_signal = _ema(valid, signal)
    signal_line: list[float | None] = []
    valid_idx = 0
    for value in macd_line:
        if value is None:
            signal_line.append(None)
        else:
            signal_line.append(valid_signal[valid_idx])
            valid_idx += 1
    histogram = [None if m is None or s is None else m - s for m, s in zip(macd_line, signal_line)]
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def ichimoku_series(bars: list[PriceBar]) -> dict[str, list[float | None]]:
    tenkan: list[float | None] = []
    kijun: list[float | None] = []
    span_a: list[float | None] = []
    span_b: list[float | None] = []
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    for idx in range(len(bars)):
        if idx + 1 >= 9:
            tenkan.append((max(highs[idx - 8 : idx + 1]) + min(lows[idx - 8 : idx + 1])) / 2.0)
        else:
            tenkan.append(None)
        if idx + 1 >= 26:
            kijun.append((max(highs[idx - 25 : idx + 1]) + min(lows[idx - 25 : idx + 1])) / 2.0)
        else:
            kijun.append(None)
        if tenkan[-1] is not None and kijun[-1] is not None:
            span_a.append((tenkan[-1] + kijun[-1]) / 2.0)
        else:
            span_a.append(None)
        if idx + 1 >= 52:
            span_b.append((max(highs[idx - 51 : idx + 1]) + min(lows[idx - 51 : idx + 1])) / 2.0)
        else:
            span_b.append(None)
    return {"tenkan": tenkan, "kijun": kijun, "span_a": span_a, "span_b": span_b}


def _last_valid(values: list[float | None]) -> float | None:
    for value in reversed(values):
        if value is not None:
            return value
    return None


def _rsi_score(rsi: list[float | None]) -> tuple[float, dict[str, Any], list[str]]:
    blocks: list[str] = []
    latest = _last_valid(rsi)
    valid = [v for v in rsi if v is not None]
    prior_values = [v for v in rsi[:-1] if v is not None]
    recent_min = min(prior_values[-30:]) if prior_values else None

    # In the 1-2-6 interpretation, RSI is an earlier stage-1 trigger.  By the
    # time MACD and Ichimoku confirm, latest RSI can already be above the ideal
    # 40~70 band.  Therefore detect a recent recovery event, not only the final
    # bar's RSI value.
    recent = valid[-40:]
    recovered_from_30 = any(prev <= 30 < curr for prev, curr in zip(recent, recent[1:]))
    recovered_trend_band = any(prev < 45 <= curr <= 75 for prev, curr in zip(recent, recent[1:])) or (latest is not None and 40 <= latest <= 75)

    score = 0.0
    band = "missing"
    if latest is None:
        blocks.append("rsi_signal_not_confirmed")
    elif recovered_from_30:
        score = 15.0
        band = "oversold_recovery"
    elif recovered_trend_band:
        score = 12.0
        band = "trend_recovery_40_75"
    else:
        band = "not_confirmed"
        blocks.append("rsi_signal_not_confirmed")

    if latest is not None and latest >= 90:
        band = f"{band}_but_overheated" if score else "overheated"
        blocks.append("fujimoto_rsi_overheated")
    return score, {"score": score, "latest": _round(latest), "recent_min": _round(recent_min), "band": band}, blocks


def _macd_score(macd: dict[str, list[float | None]]) -> tuple[float, dict[str, Any], list[str]]:
    blocks: list[str] = []
    line = macd["macd"]
    sig = macd["signal"]
    hist = macd["histogram"]
    latest_line = _last_valid(line)
    latest_sig = _last_valid(sig)
    latest_hist = _last_valid(hist)
    prev_hist = None
    valid_hist = [v for v in hist if v is not None]
    if len(valid_hist) >= 2:
        prev_hist = valid_hist[-2]
    bullish = latest_line is not None and latest_sig is not None and latest_line > latest_sig
    improving = latest_hist is not None and prev_hist is not None and latest_hist > prev_hist
    score = 0.0
    if bullish and latest_hist is not None and latest_hist > 0:
        score = 20.0
    elif bullish or improving:
        score = 12.0
    else:
        blocks.append("macd_signal_not_confirmed")
    return score, {
        "score": score,
        "macd": _round(latest_line),
        "signal": _round(latest_sig),
        "histogram": _round(latest_hist),
        "histogram_improving": improving,
        "bullish": bullish,
    }, blocks


def _ichimoku_score(bars: list[PriceBar], ichi: dict[str, list[float | None]]) -> tuple[float, dict[str, Any], list[str]]:
    blocks: list[str] = []
    span_a = ichi["span_a"]
    span_b = ichi["span_b"]
    tenkan = _last_valid(ichi["tenkan"])
    kijun = _last_valid(ichi["kijun"])
    latest_a = _last_valid(span_a)
    latest_b = _last_valid(span_b)
    latest_close = bars[-1].close if bars else None
    if latest_a is None or latest_b is None or latest_close is None:
        return 0.0, {
            "score": 0.0,
            "close": _round(latest_close),
            "span_a": _round(latest_a),
            "span_b": _round(latest_b),
            "tenkan": _round(tenkan),
            "kijun": _round(kijun),
            "cloud_state": "insufficient",
        }, ["insufficient_intraday_bars_for_ichimoku", "ichimoku_cloud_not_confirmed"]
    cloud_top = max(latest_a, latest_b)
    cloud_bottom = min(latest_a, latest_b)
    above_cloud = latest_close > cloud_top
    tenkan_above_kijun = tenkan is not None and kijun is not None and tenkan >= kijun
    prior_touch = False
    for idx, bar in enumerate(bars[-20:-1], start=max(0, len(bars) - 20)):
        a = span_a[idx]
        b = span_b[idx]
        if a is None or b is None:
            continue
        top = max(a, b)
        bottom = min(a, b)
        if bar.low <= top and bar.high >= bottom:
            prior_touch = True
            break
    score = 0.0
    if above_cloud and tenkan_above_kijun:
        score = 30.0 if prior_touch else 24.0
    elif above_cloud:
        score = 18.0
    else:
        blocks.append("ichimoku_cloud_not_confirmed")
    return score, {
        "score": score,
        "close": _round(latest_close),
        "span_a": _round(latest_a),
        "span_b": _round(latest_b),
        "cloud_top": _round(cloud_top),
        "cloud_bottom": _round(cloud_bottom),
        "tenkan": _round(tenkan),
        "kijun": _round(kijun),
        "above_cloud": above_cloud,
        "tenkan_above_kijun": tenkan_above_kijun,
        "prior_cloud_touch_or_retest": prior_touch,
        "cloud_state": "above" if above_cloud else "inside_or_below",
    }, blocks


def _market_and_risk_scores(bars: list[PriceBar], *, max_intraday_risk_pct: float) -> tuple[float, float, dict[str, Any], dict[str, Any], list[str]]:
    blocks: list[str] = []
    closes = [bar.close for bar in bars]
    volumes = [bar.volume for bar in bars]
    market_score = 0.0
    if len(closes) >= 6 and closes[-1] > closes[-6]:
        market_score += 6.0
    if len(volumes) >= 6 and mean(volumes[-5:]) >= mean(volumes[:-5] or volumes[-5:]):
        market_score += 4.0
    if market_score == 0:
        blocks.append("market_regime_not_confirmed")

    risk_score = 15.0
    intraday_risk_pct = None
    if bars:
        recent_low = min(bar.low for bar in bars[-20:])
        if bars[-1].close:
            intraday_risk_pct = (bars[-1].close - recent_low) / bars[-1].close * 100.0
            if intraday_risk_pct > max_intraday_risk_pct:
                blocks.append("risk_per_trade_exceeds_limit")
                risk_score = 5.0
    return market_score, risk_score, {"score": market_score}, {"score": risk_score, "intraday_risk_pct": _round(intraday_risk_pct), "max_intraday_risk_pct": max_intraday_risk_pct}, blocks


def evaluate_fujimoto_126(
    bars: list[PriceBar],
    *,
    min_score: float = 60.0,
    max_intraday_risk_pct: float = 2.0,
    include_order_blocks: bool = True,
) -> dict[str, Any]:
    """Evaluate a Fujimoto 1-2-6 candidate from minute bars.

    Returns a machine-readable score breakdown and blocking_conditions.  The
    `min_score` gate is for research/backtest candidate classification only; it
    does not enable orders.
    """
    if not bars:
        return {
            "strategy": STRATEGY_ID,
            "signal": "BLOCKED",
            "position_stage": "NONE",
            "score_total": 0.0,
            "score_details": {},
            "blocking_conditions": ["missing_intraday_bars", *ORDER_BLOCKS] if include_order_blocks else ["missing_intraday_bars"],
            "paper_order_allowed": False,
            "real_order_allowed": False,
            "order_execution_enabled": False,
        }
    closes = [bar.close for bar in bars]
    rsi = rsi_series(closes)
    macd = macd_series(closes)
    ichi = ichimoku_series(bars)
    rsi_score, rsi_details, rsi_blocks = _rsi_score(rsi)
    macd_score, macd_details, macd_blocks = _macd_score(macd)
    ichi_score, ichi_details, ichi_blocks = _ichimoku_score(bars, ichi)
    market_score, risk_score, market_details, risk_details, risk_blocks = _market_and_risk_scores(bars, max_intraday_risk_pct=max_intraday_risk_pct)
    # Fundamental/candidate-quality score is intentionally neutral in pure intraday mode.
    candidate_quality_score = 0.0
    candidate_blocks = ["candidate_quality_external_data_not_supplied"]

    score_total = round(rsi_score + macd_score + ichi_score + market_score + candidate_quality_score + risk_score, 4)
    stage = "NONE"
    units = 0
    if rsi_score > 0:
        stage = "STAGE1"
        units = 1
    if rsi_score > 0 and macd_score > 0:
        stage = "STAGE2"
        units = 3
    if rsi_score > 0 and macd_score > 0 and ichi_score > 0:
        stage = "STAGE3"
        units = 9

    blocking_conditions = rsi_blocks + macd_blocks + ichi_blocks + risk_blocks + candidate_blocks
    if score_total < min_score:
        blocking_conditions.append("fujimoto_score_below_min")
    if stage != "STAGE3":
        blocking_conditions.append("fujimoto_full_126_stage_not_confirmed")
    if include_order_blocks:
        blocking_conditions.extend(ORDER_BLOCKS)

    if stage == "STAGE3" and score_total >= min_score:
        signal = "HIGH_CONFIDENCE_CANDIDATE"
    elif stage in {"STAGE1", "STAGE2"}:
        signal = "WATCH"
    else:
        signal = "BLOCKED"

    return {
        "strategy": STRATEGY_ID,
        "signal": signal,
        "position_stage": stage,
        "position_units": units,
        "score_total": score_total,
        "score_details": {
            "rsi_recovery": rsi_details,
            "macd_confirmation": macd_details,
            "ichimoku_confirmation": ichi_details,
            "market_regime": market_details,
            "candidate_quality": {"score": candidate_quality_score, "status": "external_daily_fundamental_data_not_supplied"},
            "risk_control": risk_details,
            "thresholds": {"min_score": min_score, "stage_units": {"STAGE1": 1, "STAGE2": 3, "STAGE3": 9}},
        },
        "blocking_conditions": list(dict.fromkeys(blocking_conditions)),
        "paper_order_allowed": False,
        "real_order_allowed": False,
        "order_execution_enabled": False,
    }


def simulate_fujimoto_126_trade(
    bars: list[PriceBar],
    *,
    min_score: float = 60.0,
    stop_loss_pct: float = -2.0,
    take_profit_pct: float = 3.0,
    time_exit: str = "15:20",
    fee_bps: float = 23.0,
    slippage_bps: float = 10.0,
) -> dict[str, Any]:
    """Simulate one read-only intraday trade from first full 1-2-6 confirmation."""
    if not bars:
        return {"ok": False, "blocking_conditions": ["missing_intraday_bars", *ORDER_BLOCKS], "paper_order_allowed": False, "real_order_allowed": False, "order_execution_enabled": False}
    entry_eval = None
    entry_idx = None
    for idx in range(len(bars)):
        result = evaluate_fujimoto_126(bars[: idx + 1], min_score=min_score)
        if result["signal"] == "HIGH_CONFIDENCE_CANDIDATE":
            entry_eval = result
            entry_idx = idx
            break
    if entry_eval is None or entry_idx is None:
        final_eval = evaluate_fujimoto_126(bars, min_score=min_score)
        return {"ok": False, **final_eval}

    entry_bar = bars[entry_idx]
    entry_price = entry_bar.close
    exit_price = bars[-1].close
    exit_time = bars[-1].hhmm
    exit_reason = "last_close_exit"
    for bar in bars[entry_idx + 1 :]:
        low_ret = (bar.low - entry_price) / entry_price * 100.0 if entry_price else 0.0
        high_ret = (bar.high - entry_price) / entry_price * 100.0 if entry_price else 0.0
        if low_ret <= stop_loss_pct:
            exit_price = entry_price * (1 + stop_loss_pct / 100.0)
            exit_time = bar.hhmm
            exit_reason = "STOP_LOSS_SIGNAL"
            break
        if high_ret >= take_profit_pct:
            exit_price = entry_price * (1 + take_profit_pct / 100.0)
            exit_time = bar.hhmm
            exit_reason = "TAKE_PROFIT_SIGNAL"
            break
        if bar.hhmm >= time_exit:
            exit_price = bar.close
            exit_time = bar.hhmm
            exit_reason = "TIME_EXIT_SIGNAL"
            break
    gross = (exit_price - entry_price) / entry_price * 100.0 if entry_price else 0.0
    cost = ((fee_bps + slippage_bps) / 100.0) * 2.0
    return {
        "ok": True,
        "strategy": STRATEGY_ID,
        "entry_time": entry_bar.hhmm,
        "entry_price": _round(entry_price),
        "entry_stage": entry_eval["position_stage"],
        "position_units": entry_eval["position_units"],
        "entry_score_total": entry_eval["score_total"],
        "entry_score_details": entry_eval["score_details"],
        "exit_time": exit_time,
        "exit_price": _round(exit_price),
        "exit_reason": exit_reason,
        "gross_return_pct": _round(gross),
        "cost_pct": _round(cost),
        "net_return_pct": _round(gross - cost),
        "blocking_conditions": entry_eval["blocking_conditions"],
        "paper_order_allowed": False,
        "real_order_allowed": False,
        "order_execution_enabled": False,
    }
