"""Analyze low-area BUY and high-area SELL signal markers on real ka10080 1-minute charts.

Read-only research script for Shigeru/Fujimoto applicability upgrade.

Outputs:
- Markdown report reviewing which signals are usable near intraday lows/highs.
- PNG charts with stock names, signal markers, entry and exit markers.

Safety:
- Reads only Supabase/Postgres tables.
- Uses intraday_prices source=kiwoom_ka10080_minute, time_frame=1min.
- Does not write orders/positions and does not call order APIs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.fujimoto_126_filter import PriceBar, evaluate_fujimoto_126, macd_series, rsi_series  # noqa: E402
from core.supabase_rest import read_env  # noqa: E402

KST = timezone(timedelta(hours=9))
SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"


def num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def ts_to_kst(value: Any) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text) if not isinstance(value, datetime) else value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


@dataclass
class Marker:
    idx: int
    hhmm: str
    price: float
    kind: str
    label: str
    score: int
    dist_low_pct: float | None = None
    dist_high_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "idx": self.idx,
            "hhmm": self.hhmm,
            "price": round(self.price, 4),
            "kind": self.kind,
            "label": self.label,
            "score": self.score,
            "dist_low_pct": None if self.dist_low_pct is None else round(self.dist_low_pct, 4),
            "dist_high_pct": None if self.dist_high_pct is None else round(self.dist_high_pct, 4),
        }


def fetch_stock_names(cur: Any, stock_codes: list[str]) -> dict[str, str]:
    cur.execute(
        "select stock_code, stock_name from kospi_top50 where stock_code = any(%s)",
        (stock_codes,),
    )
    return {str(code): str(name) for code, name in cur.fetchall() if name}


def fetch_bars(cur: Any, stock_code: str, trading_day: date) -> list[PriceBar]:
    cur.execute(
        """
        select timestamp, open, high, low, close, volume
        from intraday_prices
        where stock_code=%s and source=%s and time_frame=%s
          and (timestamp at time zone 'Asia/Seoul')::date=%s
        order by timestamp asc
        """,
        (stock_code, SOURCE, TIME_FRAME, trading_day),
    )
    bars: list[PriceBar] = []
    for ts, o, h, l, c, v in cur.fetchall():
        kst = ts_to_kst(ts)
        bars.append(PriceBar(kst, kst.strftime("%H:%M"), num(o), num(h), num(l), num(c), int(v or 0)))
    return bars


def fetch_stock_days(cur: Any, stock_codes: list[str], days: int, limit_days: int) -> list[tuple[str, date]]:
    since = (datetime.now(KST).date() - timedelta(days=days))
    cur.execute(
        """
        select stock_code, (timestamp at time zone 'Asia/Seoul')::date as trading_day, count(*) as rows
        from intraday_prices
        where stock_code = any(%s) and source=%s and time_frame=%s
          and (timestamp at time zone 'Asia/Seoul')::date >= %s
        group by stock_code, (timestamp at time zone 'Asia/Seoul')::date
        having count(*) >= 120
        order by trading_day desc, stock_code asc
        limit %s
        """,
        (stock_codes, SOURCE, TIME_FRAME, since, limit_days),
    )
    return [(str(code), day) for code, day, _rows in cur.fetchall()]


def moving_average(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for idx in range(len(values)):
        if idx + 1 < window:
            out.append(None)
        else:
            out.append(sum(values[idx + 1 - window : idx + 1]) / window)
    return out


def is_near_low(price: float, day_low: float) -> float:
    return (price - day_low) / price * 100.0 if price else 999.0


def is_near_high(price: float, day_high: float) -> float:
    return (day_high - price) / price * 100.0 if price else 999.0


def first_or_trade(bars: list[PriceBar], window: int = 10) -> dict[str, Any] | None:
    range_end = "09:10" if window == 10 else "09:30"
    range_rows = [b for b in bars if "09:00" <= b.hhmm <= range_end]
    if len({b.hhmm for b in range_rows}) < window + 1:
        return None
    opening_high = max(b.high for b in range_rows)
    for idx, bar in enumerate(bars):
        if bar.hhmm > range_end and bar.high > opening_high:
            return {"idx": idx, "hhmm": bar.hhmm, "price": bar.close, "opening_high": opening_high, "range_end": range_end}
    return None


def make_markers(bars: list[PriceBar]) -> dict[str, Any]:
    closes = [b.close for b in bars]
    volumes = [b.volume for b in bars]
    rsis = rsi_series(closes)
    macd = macd_series(closes)
    hist = macd["histogram"]
    day_low = min(b.low for b in bars)
    day_high = max(b.high for b in bars)
    buy: list[Marker] = []
    sell: list[Marker] = []
    stage_markers: list[Marker] = []
    seen_stage: set[str] = set()

    for idx, bar in enumerate(bars):
        if idx < 15:
            continue
        prev = bars[idx - 1]
        recent_lows = [b.low for b in bars[max(0, idx - 10) : idx + 1]]
        recent_highs = [b.high for b in bars[max(0, idx - 10) : idx + 1]]
        recent_vols = volumes[max(0, idx - 20) : idx]
        avg_prev_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 0
        rsi = rsis[idx]
        prev_rsi = rsis[idx - 1] if idx > 0 else None
        h = hist[idx]
        prev_h = hist[idx - 1] if idx > 0 else None
        dist_low = is_near_low(bar.close, day_low)
        dist_high = is_near_high(bar.close, day_high)
        vol_ok = avg_prev_vol > 0 and bar.volume >= avg_prev_vol * 1.2

        # BUY candidates: these intentionally favor rebound near final/rolling low, not breakout chasing.
        if bar.low <= min(recent_lows) * 1.003 and bar.close > prev.close and dist_low <= 1.2:
            score = 2 + int(vol_ok) + int(rsi is not None and rsi <= 45) + int(h is not None and prev_h is not None and h > prev_h)
            buy.append(Marker(idx, bar.hhmm, bar.close, "BUY", "저점반등", score, dist_low_pct=dist_low, dist_high_pct=dist_high))
        if prev_rsi is not None and rsi is not None and prev_rsi < 40 <= rsi and dist_low <= 2.0:
            score = 2 + int(h is not None and prev_h is not None and h > prev_h) + int(vol_ok)
            buy.append(Marker(idx, bar.hhmm, bar.close, "BUY", "RSI40회복", score, dist_low_pct=dist_low, dist_high_pct=dist_high))
        if h is not None and prev_h is not None and prev_h <= 0 < h and dist_low <= 2.5:
            score = 2 + int(rsi is not None and 35 <= rsi <= 65) + int(bar.close > prev.close)
            buy.append(Marker(idx, bar.hhmm, bar.close, "BUY", "MACD전환", score, dist_low_pct=dist_low, dist_high_pct=dist_high))

        # SELL candidates: high rejection/overheat/momentum loss near final/rolling high.
        bearish_candle = bar.close < bar.open or bar.close < prev.close
        if bar.high >= max(recent_highs) * 0.997 and bearish_candle and dist_high <= 1.2:
            score = 2 + int(rsi is not None and rsi >= 60) + int(h is not None and prev_h is not None and h < prev_h) + int(vol_ok)
            sell.append(Marker(idx, bar.hhmm, bar.close, "SELL", "고점거부", score, dist_low_pct=dist_low, dist_high_pct=dist_high))
        if prev_rsi is not None and rsi is not None and prev_rsi >= 70 > rsi and dist_high <= 2.0:
            score = 2 + int(h is not None and prev_h is not None and h < prev_h) + int(bearish_candle)
            sell.append(Marker(idx, bar.hhmm, bar.close, "SELL", "RSI70이탈", score, dist_low_pct=dist_low, dist_high_pct=dist_high))
        if h is not None and prev_h is not None and prev_h >= 0 > h and dist_high <= 2.5:
            score = 2 + int(rsi is not None and rsi >= 55) + int(bearish_candle)
            sell.append(Marker(idx, bar.hhmm, bar.close, "SELL", "MACD둔화", score, dist_low_pct=dist_low, dist_high_pct=dist_high))

        # Shigeru/Fujimoto staged confirmation markers for visual review.
        ev = evaluate_fujimoto_126(bars[: idx + 1], min_score=60.0, include_order_blocks=False)
        stage = ev.get("position_stage")
        if stage in {"STAGE1", "STAGE2", "STAGE3"} and stage not in seen_stage:
            seen_stage.add(stage)
            stage_markers.append(Marker(idx, bar.hhmm, bar.close, "SHIGERU", str(stage), int(ev.get("score_total") or 0), dist_low_pct=dist_low, dist_high_pct=dist_high))

    def dedupe(items: list[Marker], min_gap: int = 8) -> list[Marker]:
        out: list[Marker] = []
        for item in sorted(items, key=lambda m: (-m.score, m.idx)):
            if all(abs(item.idx - prior.idx) >= min_gap or item.label != prior.label for prior in out):
                out.append(item)
        return sorted(out, key=lambda m: m.idx)

    return {
        "day_low": day_low,
        "day_high": day_high,
        "buy_markers": dedupe(buy),
        "sell_markers": dedupe(sell),
        "stage_markers": stage_markers,
    }


def summarize_markers(markers: list[Marker], near_field: str, threshold: float = 0.7) -> dict[str, Any]:
    if not markers:
        return {"count": 0, "near_count": 0, "near_rate_pct": None, "avg_distance_pct": None, "labels": {}}
    values = [getattr(m, near_field) for m in markers if getattr(m, near_field) is not None]
    near = [v for v in values if v is not None and v <= threshold]
    return {
        "count": len(markers),
        "near_count": len(near),
        "near_rate_pct": round(len(near) / len(markers) * 100.0, 2) if markers else None,
        "avg_distance_pct": round(sum(values) / len(values), 4) if values else None,
        "labels": dict(Counter(m.label for m in markers)),
    }


def plot_chart(
    bars: list[PriceBar],
    stock_code: str,
    stock_name: str,
    trading_day: date,
    markers: dict[str, Any],
    out_path: Path,
    *,
    or_window: int,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.patches import Rectangle

    # Ensure Korean stock names and labels render in PNG artifacts.
    for font_path in [
        "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    ]:
        if Path(font_path).exists():
            font_manager.fontManager.addfont(font_path)
            font_name = font_manager.FontProperties(fname=font_path).get_name()
            plt.rcParams["font.family"] = font_name
            break
    plt.rcParams["axes.unicode_minus"] = False

    x = list(range(len(bars)))
    closes = [b.close for b in bars]
    ma5 = moving_average(closes, 5)
    ma20 = moving_average(closes, 20)
    ma60 = moving_average(closes, 60)
    trade = first_or_trade(bars, or_window)
    exit_idx = len(bars) - 1

    fig, (ax, axv) = plt.subplots(2, 1, figsize=(18, 10), sharex=True, gridspec_kw={"height_ratios": [4, 1]})
    fig.patch.set_facecolor("#0b1020")
    for a in (ax, axv):
        a.set_facecolor("#111827")
        a.grid(True, color="#263244", linewidth=0.5, alpha=0.7)
        a.tick_params(colors="#d1d5db")
        for spine in a.spines.values():
            spine.set_color("#475569")

    width = 0.65
    for idx, bar in enumerate(bars):
        up = bar.close >= bar.open
        color = "#ef4444" if up else "#3b82f6"  # Korean convention: up red, down blue
        ax.vlines(idx, bar.low, bar.high, color=color, linewidth=0.8, alpha=0.9)
        low_body = min(bar.open, bar.close)
        height = max(abs(bar.close - bar.open), 0.01)
        ax.add_patch(Rectangle((idx - width / 2, low_body), width, height, facecolor=color, edgecolor=color, alpha=0.85))
        axv.bar(idx, bar.volume, color=color, width=0.8, alpha=0.65)

    for vals, color, label, lw in [(ma5, "#facc15", "MA5", 1.1), (ma20, "#22c55e", "MA20", 1.1), (ma60, "#a78bfa", "MA60", 1.0)]:
        ax.plot(x, [v if v is not None else float("nan") for v in vals], color=color, linewidth=lw, label=label)

    ax.axhline(markers["day_low"], color="#22c55e", linestyle=":", linewidth=1.0, alpha=0.8, label="당일 최저가")
    ax.axhline(markers["day_high"], color="#fb7185", linestyle=":", linewidth=1.0, alpha=0.8, label="당일 최고가")

    if trade:
        ax.scatter([trade["idx"]], [trade["price"]], marker="^", s=190, color="#10b981", edgecolor="white", zorder=7, label="OR 진입")
        ax.annotate(f"OR진입 {trade['hhmm']}", xy=(trade["idx"], trade["price"]), xytext=(10, 26), textcoords="offset points", color="#86efac", arrowprops={"arrowstyle": "->", "color": "#86efac"})
        ax.axhline(trade["opening_high"], color="#f59e0b", linestyle="--", linewidth=1.0, label=f"OR{or_window} 고가")
    ax.scatter([exit_idx], [bars[-1].close], marker="v", s=170, color="#f97316", edgecolor="white", zorder=7, label="기존 청산")
    ax.annotate(f"청산 {bars[-1].hhmm}", xy=(exit_idx, bars[-1].close), xytext=(-80, -34), textcoords="offset points", color="#fdba74", arrowprops={"arrowstyle": "->", "color": "#fdba74"})

    # Limit labels to keep charts readable.
    for marker in markers["buy_markers"][:8]:
        ax.scatter([marker.idx], [marker.price], marker="o", s=80 + marker.score * 15, color="#22c55e", edgecolor="white", zorder=6, alpha=0.95)
        ax.annotate(marker.label, xy=(marker.idx, marker.price), xytext=(4, 14), textcoords="offset points", color="#bbf7d0", fontsize=9)
    for marker in markers["sell_markers"][:8]:
        ax.scatter([marker.idx], [marker.price], marker="X", s=80 + marker.score * 15, color="#ef4444", edgecolor="white", zorder=6, alpha=0.95)
        ax.annotate(marker.label, xy=(marker.idx, marker.price), xytext=(4, -18), textcoords="offset points", color="#fecaca", fontsize=9)
    for marker in markers["stage_markers"]:
        color = {"STAGE1": "#60a5fa", "STAGE2": "#c084fc", "STAGE3": "#facc15"}.get(marker.label, "#e5e7eb")
        ax.scatter([marker.idx], [marker.price], marker="*", s=230, color=color, edgecolor="black", zorder=8, label=f"시게루 {marker.label}")
        ax.annotate(marker.label, xy=(marker.idx, marker.price), xytext=(6, -32), textcoords="offset points", color=color, fontsize=9)

    tick_step = max(1, len(bars) // 14)
    ticks = x[::tick_step]
    axv.set_xticks(ticks)
    axv.set_xticklabels([bars[idx].hhmm for idx in ticks], rotation=45, ha="right", color="#d1d5db")
    ax.set_ylabel("가격", color="#d1d5db")
    axv.set_ylabel("거래량", color="#d1d5db")
    title = f"{stock_name} ({stock_code}) {trading_day} | 저점권 매수·고점권 매도 신호 검토 + 시게루 단계 마킹"
    ax.set_title(title, color="white", fontsize=15)
    ax.legend(loc="upper left", fontsize=9, facecolor="#111827", edgecolor="#475569", labelcolor="#e5e7eb", ncol=2)
    fig.text(0.01, 0.01, "데이터: Kiwoom ka10080 1분봉 / read-only / paper·real 주문 금지", color="#cbd5e1", fontsize=9)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.03, 1, 0.98))
    fig.savefig(out_path, dpi=140, facecolor=fig.get_facecolor())
    plt.close(fig)


def write_report(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    chart_rows = payload["charts"]
    lines = [
        "# 저점권 매수·고점권 매도 신호 검토 리포트",
        "",
        f"- 생성 시각: `{payload['generated_at']}`",
        f"- 데이터: `intraday_prices`, source=`{SOURCE}`, time_frame=`{TIME_FRAME}`",
        "- 목적: 기존 진입/청산 차트에 **신호 마킹**을 추가하고, 시게루 1-2-6 적용성을 업그레이드하기 위한 후보 신호 검토",
        "- 안전 상태: read-only 분석, 주문/포지션 미변경, paper/real 주문 금지",
        "",
        "## 1) 집계 요약",
        "",
        "| 구분 | 전체 신호 | 극값 근처 신호 | 극값 근처 비율 | 평균 거리 | 라벨 분포 |",
        "|---|---:|---:|---:|---:|---|",
        f"| 매수 후보(당일 최저가 기준) | {summary['buy']['count']} | {summary['buy']['near_count']} | {summary['buy']['near_rate_pct']}% | {summary['buy']['avg_distance_pct']}% | `{json.dumps(summary['buy']['labels'], ensure_ascii=False)}` |",
        f"| 매도 후보(당일 최고가 기준) | {summary['sell']['count']} | {summary['sell']['near_count']} | {summary['sell']['near_rate_pct']}% | {summary['sell']['avg_distance_pct']}% | `{json.dumps(summary['sell']['labels'], ensure_ascii=False)}` |",
        "",
        "판정 기준: 매수는 신호가격이 당일 최저가에서 0.7% 이내, 매도는 신호가격이 당일 최고가에서 0.7% 이내이면 `극값 근처`로 집계했습니다.",
        "",
        "## 2) 사용할 신호 후보 판단",
        "",
        "| 우선순위 | 신호 | 사용 방향 | 이유 |",
        "|---:|---|---|---|",
        "| 1 | 저점반등 + RSI40회복이 겹치는 매수 | 시게루 STAGE1 조기 관찰 신호 | 최저가 근처 반등을 직접 잡고, 공포로 진입을 놓치는 문제를 줄이는 데 적합 |",
        "| 2 | MACD전환 매수 | STAGE2 확인/추가 검증 신호 | 저점반등 단독보다 늦지만 추세 반전 확인력이 있어 오진입을 줄이는 후보 |",
        "| 3 | 고점거부 + RSI70이탈 매도 | 익절/분할청산 후보 | 최고가 근처에서 되밀림을 표시하므로 탐욕으로 청산을 놓치는 문제 완화에 적합 |",
        "| 4 | MACD둔화 매도 | 보조 청산/경고 신호 | 고점보다 늦게 나올 수 있어 단독 청산보다 경고·확인용이 적합 |",
        "",
        "## 3) 시게루 적용성 버전업 제안",
        "",
        "- 기존 시게루 STAGE3는 안전하지만 늦게 찍힐 수 있으므로, **실매수 트리거가 아니라 STAGE1/2/3 단계 마킹을 모두 차트에 표시**하는 방향이 좋습니다.",
        "- 버전업 방향: `저점반등/RSI40회복 = STAGE1 후보`, `MACD전환 = STAGE2 확인`, `일목/추세 확인 = STAGE3 진입 확인`으로 분리합니다.",
        "- 매도는 시게루 매수전략의 빈 구간이므로 별도 `고점거부/RSI70이탈/MACD둔화` 청산 레이어를 붙이는 것이 필요합니다.",
        "- 단, 현재 결과는 신호 후보 검토이며 threshold/weight/order behavior는 변경하지 않았습니다.",
        "",
        "## 4) 생성 차트",
        "",
        "| 종목 | 날짜 | 매수후보 | 매도후보 | 차트 |",
        "|---|---|---:|---:|---|",
    ]
    for row in chart_rows:
        rel = Path(row["path"]).name
        lines.append(f"| {row['stock_name']} | {row['trading_day']} | {row['buy_count']} | {row['sell_count']} | [{rel}]({rel}) |")
    lines.extend([
        "",
        "## 5) 차트 개선 체크리스트",
        "",
        "- 종목은 코드 단독이 아니라 `삼성전자`처럼 종목명을 제목/표에 표시했습니다.",
        "- 진입/청산 마커 외에 저점권 매수 후보, 고점권 매도 후보, 시게루 STAGE1/2/3 마커를 함께 표시했습니다.",
        "- 당일 최저가/최고가 기준선을 추가해 사용자가 신호 위치를 육안으로 확인하기 쉽게 했습니다.",
        "- 다음 개선: 신호가 너무 많거나 겹치는 종목은 라벨 우선순위/필터를 더 줄이고, HTML 인터랙티브 차트에도 동일 마커를 반영합니다.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-codes", nargs="+", default=["005930", "000660", "035420", "005380", "068270"])
    parser.add_argument("--days", type=int, default=130)
    parser.add_argument("--limit-days", type=int, default=30)
    parser.add_argument("--chart-limit", type=int, default=10)
    parser.add_argument("--or-window", type=int, choices=[10, 30], default=10)
    parser.add_argument("--out-dir", default="reports/backtest_trade_charts_signal_review")
    args = parser.parse_args()

    env = read_env(PROJECT_ROOT / ".env")
    if not env.get("DATABASE_URL"):
        print(json.dumps({"ok": False, "blocking_conditions": ["missing_database_url"]}, ensure_ascii=False, indent=2))
        return 2

    import psycopg

    out_dir = PROJECT_ROOT / args.out_dir
    chart_outputs: list[dict[str, Any]] = []
    all_buy: list[Marker] = []
    all_sell: list[Marker] = []
    days_seen = 0
    blocks: list[str] = []

    with psycopg.connect(env["DATABASE_URL"], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            names = fetch_stock_names(cur, args.stock_codes)
            stock_days = fetch_stock_days(cur, args.stock_codes, args.days, args.limit_days)
            for stock_code, trading_day in stock_days:
                bars = fetch_bars(cur, stock_code, trading_day)
                if not bars:
                    blocks.append(f"missing_bars:{stock_code}:{trading_day}")
                    continue
                days_seen += 1
                markers = make_markers(bars)
                all_buy.extend(markers["buy_markers"])
                all_sell.extend(markers["sell_markers"])

                # Prefer charts that actually contain both buy and sell candidates.
                if len(chart_outputs) < args.chart_limit and (markers["buy_markers"] or markers["sell_markers"]):
                    stock_name = names.get(stock_code) or stock_code
                    out_path = out_dir / f"{trading_day}_{stock_name}_{stock_code}_signals.png"
                    plot_chart(bars, stock_code, stock_name, trading_day, markers, out_path, or_window=args.or_window)
                    chart_outputs.append({
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "trading_day": str(trading_day),
                        "buy_count": len(markers["buy_markers"]),
                        "sell_count": len(markers["sell_markers"]),
                        "stage_markers": [m.to_dict() for m in markers["stage_markers"]],
                        "path": str(out_path),
                    })

    payload = {
        "ok": True,
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "source": SOURCE,
        "time_frame": TIME_FRAME,
        "parameters": vars(args),
        "summary": {
            "stock_days_seen": days_seen,
            "buy": summarize_markers(all_buy, "dist_low_pct"),
            "sell": summarize_markers(all_sell, "dist_high_pct"),
        },
        "charts": chart_outputs,
        "blocking_conditions": blocks,
        "paper_order_allowed": False,
        "real_order_allowed": False,
        "order_execution_enabled": False,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "signal_review_summary.json"
    md_path = out_dir / "signal_review_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(md_path, payload)
    print(json.dumps({"ok": True, "json": str(json_path), "report": str(md_path), "chart_count": len(chart_outputs), "summary": payload["summary"], "blocking_conditions": blocks[:10]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
