#!/usr/bin/env python3
"""Create Samsung validation charts focused on Feb 1 ~ latest available date."""
from __future__ import annotations

from pathlib import Path
import json
import pandas as pd
import psycopg
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
REPORT_DIR = ROOT / "reports"
STOCK_CODE = "005930"
STOCK_NAME = "삼성전자"
STRATEGY = "technical_score_v1"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.split(" #", 1)[0].strip().strip('"').strip("'")
    return env


def main() -> None:
    env = load_env()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(env["DATABASE_URL"], connect_timeout=20, prepare_threshold=None) as conn:
        max_date = pd.read_sql(
            "SELECT MAX(date) AS max_date FROM daily_prices WHERE stock_code=%s AND source='kiwoom_ka10081'",
            conn,
            params=(STOCK_CODE,),
        )["max_date"].iloc[0]
        max_date = pd.to_datetime(max_date)
        start_date = pd.Timestamp(year=max_date.year, month=2, day=1)
        prices = pd.read_sql(
            """
            SELECT d.date, d.open, d.high, d.low, d.close, d.volume,
                   i.ma_5, i.ma_20, i.ma_60, i.rsi, i.macd, i.signal_line, i.macd_hist,
                   i.bb_upper, i.bb_middle, i.bb_lower, i.volume_ma
            FROM daily_prices d
            LEFT JOIN technical_indicators i
              ON i.stock_code=d.stock_code AND i.date=d.date AND i.time_frame='daily'
            WHERE d.stock_code=%s AND d.source='kiwoom_ka10081'
              AND d.date >= %s AND d.date <= %s
            ORDER BY d.date
            """,
            conn,
            params=(STOCK_CODE, start_date.date(), max_date.date()),
        )
        sigs = pd.read_sql(
            """
            SELECT signal_date, signal_type, score, price, score_details, reason
            FROM trading_signals
            WHERE stock_code=%s AND strategy=%s
              AND signal_date::date >= %s AND signal_date::date <= %s
            ORDER BY signal_date
            """,
            conn,
            params=(STOCK_CODE, STRATEGY, start_date.date(), max_date.date()),
        )

    if prices.empty:
        raise RuntimeError(f"No price rows for {STOCK_CODE} from {start_date.date()} to {max_date.date()}")

    prices["date"] = pd.to_datetime(prices["date"])
    for c in ["open", "high", "low", "close", "volume", "ma_5", "ma_20", "ma_60", "rsi", "macd", "signal_line", "macd_hist", "bb_upper", "bb_middle", "bb_lower", "volume_ma"]:
        prices[c] = pd.to_numeric(prices[c], errors="coerce")

    # Interactive validation chart
    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.52, 0.17, 0.16, 0.15],
        subplot_titles=(
            f"{STOCK_CODE} {STOCK_NAME} 가격 + MA/BB ({start_date.date()}~{max_date.date()})",
            "거래량 + Volume MA20",
            "RSI14",
            "MACD",
        ),
    )
    fig.add_trace(go.Candlestick(
        x=prices["date"], open=prices["open"], high=prices["high"], low=prices["low"], close=prices["close"],
        name="OHLC", increasing_line_color="#16a34a", decreasing_line_color="#dc2626",
    ), row=1, col=1)
    for col, color, name in [("ma_5", "#f59e0b", "MA5"), ("ma_20", "#2563eb", "MA20"), ("ma_60", "#7c3aed", "MA60"), ("bb_upper", "#94a3b8", "BB Upper"), ("bb_lower", "#94a3b8", "BB Lower")]:
        fig.add_trace(go.Scatter(x=prices["date"], y=prices[col], name=name, mode="lines", line=dict(width=1.4, color=color)), row=1, col=1)

    if not sigs.empty:
        sigs["signal_date"] = pd.to_datetime(sigs["signal_date"]).dt.tz_localize(None).dt.normalize()
        color_map = {"BUY": "#16a34a", "SELL": "#dc2626", "HOLD": "#64748b"}
        symbol_map = {"BUY": "triangle-up", "SELL": "triangle-down", "HOLD": "circle"}
        for sig_type, group in sigs.groupby("signal_type"):
            fig.add_trace(go.Scatter(
                x=group["signal_date"], y=group["price"], mode="markers+text", name=f"{sig_type} Signal",
                marker=dict(size=16, color=color_map.get(sig_type, "#64748b"), symbol=symbol_map.get(sig_type, "circle"), line=dict(color="white", width=2)),
                text=[f"{sig_type} {float(s):.0f}" for s in group["score"]],
                textposition="top center",
                hovertext=[str(x) for x in group["reason"]], hoverinfo="text",
            ), row=1, col=1)

    fig.add_trace(go.Bar(x=prices["date"], y=prices["volume"], name="Volume", marker_color="#64748b"), row=2, col=1)
    fig.add_trace(go.Scatter(x=prices["date"], y=prices["volume_ma"], name="Vol MA20", mode="lines", line=dict(color="#f97316")), row=2, col=1)
    fig.add_trace(go.Scatter(x=prices["date"], y=prices["rsi"], name="RSI14", mode="lines", line=dict(color="#0ea5e9")), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#ef4444", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#22c55e", row=3, col=1)
    fig.add_trace(go.Scatter(x=prices["date"], y=prices["macd"], name="MACD", mode="lines", line=dict(color="#2563eb")), row=4, col=1)
    fig.add_trace(go.Scatter(x=prices["date"], y=prices["signal_line"], name="MACD Signal", mode="lines", line=dict(color="#f97316")), row=4, col=1)
    fig.add_trace(go.Bar(x=prices["date"], y=prices["macd_hist"], name="MACD Hist", marker_color="#94a3b8"), row=4, col=1)
    fig.update_layout(
        template="plotly_white",
        title=f"삼성전자 검증 차트 — 2월 1일~최신일 ({start_date.date()}~{max_date.date()})",
        height=1000,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=30, t=90, b=40),
    )
    html_path = REPORT_DIR / "samsung_feb1_to_today_validation.html"
    fig.write_html(html_path, include_plotlyjs="cdn")

    # Static PNG
    png_path = REPORT_DIR / "samsung_feb1_to_today_static.png"
    fig2, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True, gridspec_kw={"height_ratios": [3, 1, 1]})
    ax = axes[0]
    ax.plot(prices["date"], prices["close"], label="Close", color="black", linewidth=1.8)
    ax.plot(prices["date"], prices["ma_5"], label="MA5", linewidth=1.2)
    ax.plot(prices["date"], prices["ma_20"], label="MA20", linewidth=1.2)
    ax.plot(prices["date"], prices["ma_60"], label="MA60", linewidth=1.2)
    ax.fill_between(prices["date"], prices["low"], prices["high"], color="gray", alpha=0.15, label="Low~High")
    if not sigs.empty:
        latest = sigs.iloc[-1]
        ax.scatter([latest["signal_date"]], [float(latest["price"])], s=180, marker="^" if latest["signal_type"] == "BUY" else "v", color="#16a34a" if latest["signal_type"] == "BUY" else "#dc2626", zorder=5)
        ax.text(latest["signal_date"], float(latest["price"]), f" {latest['signal_type']} {float(latest['score']):.0f}", fontsize=11, weight="bold")
    ax.set_title(f"Samsung Electronics 005930 — {start_date.date()} to {max_date.date()}")
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", ncol=6)
    axes[1].bar(prices["date"], prices["volume"], color="slategray", alpha=0.75, label="Volume")
    axes[1].plot(prices["date"], prices["volume_ma"], color="orange", label="Volume MA20")
    axes[1].set_ylabel("Volume")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="upper left")
    ret = prices["close"].pct_change() * 100
    axes[2].plot(prices["date"], ret, color="purple", label="Daily Return %")
    axes[2].axhline(0, color="black", linewidth=0.8)
    axes[2].set_ylabel("Return %")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="upper left")
    fig2.tight_layout()
    fig2.savefig(png_path, dpi=160)

    report_path = REPORT_DIR / "samsung_feb1_to_today_summary.md"
    latest_signal = None
    if not sigs.empty:
        last = sigs.iloc[-1]
        details = last["score_details"] if isinstance(last["score_details"], dict) else json.loads(last["score_details"])
        latest_signal = {
            "date": str(last["signal_date"].date()),
            "signal": last["signal_type"],
            "score": float(last["score"]),
            "price": float(last["price"]),
            "details": details,
        }
    lines = [
        "# 삼성전자 2월 1일~최신일 차트 요약",
        "",
        f"- 기간: `{start_date.date()} ~ {max_date.date()}`",
        f"- 가격 rows: `{len(prices)}`",
        f"- 신호 rows: `{len(sigs)}`",
        f"- HTML: `{html_path}`",
        f"- PNG: `{png_path}`",
        "",
        "## 최신 신호",
    ]
    if latest_signal:
        lines += [
            f"- signal: **{latest_signal['signal']}**",
            f"- score: `{latest_signal['score']}`",
            f"- price: `{latest_signal['price']}`",
            f"- total: `{latest_signal['details'].get('total')}`",
            f"- trend: `{latest_signal['details'].get('trend')}`",
            f"- momentum: `{latest_signal['details'].get('momentum')}`",
            f"- macd: `{latest_signal['details'].get('macd')}`",
            f"- volume: `{latest_signal['details'].get('volume')}`",
        ]
    else:
        lines.append("- 이 기간의 저장된 신호 없음")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"start={start_date.date()}, end={max_date.date()}, price_rows={len(prices)}, signal_rows={len(sigs)}")
    print(f"html={html_path}")
    print(f"png={png_path}")
    print(f"summary={report_path}")


if __name__ == "__main__":
    main()
