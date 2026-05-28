#!/usr/bin/env python3
"""Samsung Electronics data validation dashboard.

- Reads Kiwoom daily_prices from Supabase/Postgres.
- Fetches external KRX baseline through pykrx.
- Produces HTML chart, PNG chart (if kaleido works), CSV comparison, and Markdown report.
- Does not generate fake market data.
"""
from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import psycopg
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
REPORT_DIR = ROOT / "reports"
STOCK_CODE = "005930"
STOCK_NAME = "삼성전자"
SOURCE = "kiwoom_ka10081"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.split(" #", 1)[0].strip().strip('"').strip("'")
    return env


def read_kiwoom_df(database_url: str) -> pd.DataFrame:
    sql = """
        SELECT date, open, high, low, close, volume, trading_value, source
        FROM daily_prices
        WHERE stock_code = %s AND source = %s
        ORDER BY date
    """
    with psycopg.connect(database_url, connect_timeout=20, prepare_threshold=None) as conn:
        df = pd.read_sql(sql, conn, params=(STOCK_CODE, SOURCE))
    if df.empty:
        raise RuntimeError("DB에 삼성전자 Kiwoom 일봉 데이터가 없습니다.")
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "volume", "trading_value"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ma5"] = out["close"].rolling(5).mean()
    out["ma20"] = out["close"].rolling(20).mean()
    out["ma60"] = out["close"].rolling(60).mean()
    out["vol_ma20"] = out["volume"].rolling(20).mean()
    delta = out["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, pd.NA)
    out["rsi14"] = 100 - (100 / (1 + rs))
    ema12 = out["close"].ewm(span=12, adjust=False).mean()
    ema26 = out["close"].ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    mid = out["close"].rolling(20).mean()
    std = out["close"].rolling(20).std()
    out["bb_upper"] = mid + 2 * std
    out["bb_lower"] = mid - 2 * std
    out["daily_return_pct"] = out["close"].pct_change() * 100
    out["hl_range_pct"] = ((out["high"] - out["low"]) / out["close"].replace(0, pd.NA)) * 100
    vol_mean = out["volume"].rolling(60).mean()
    vol_std = out["volume"].rolling(60).std()
    out["volume_z60"] = (out["volume"] - vol_mean) / vol_std.replace(0, pd.NA)
    return out


def quality_checks(df: pd.DataFrame) -> dict[str, Any]:
    ohlc_bad = df[
        (df["low"] > df[["open", "high", "close"]].min(axis=1))
        | (df["high"] < df[["open", "low", "close"]].max(axis=1))
        | (df[["open", "high", "low", "close"]].isna().any(axis=1))
        | (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    ]
    dup_count = int(df.duplicated(subset=["date"]).sum())
    huge_return = df[df["daily_return_pct"].abs() > 30]
    huge_range = df[df["hl_range_pct"] > 30]
    vol_spike = df[df["volume_z60"].abs() > 5]
    # Business-day gap is informational only because KRX holidays are excluded.
    bdays = pd.date_range(df["date"].min(), df["date"].max(), freq="B")
    missing_bdays = sorted(set(bdays.date) - set(df["date"].dt.date))
    return {
        "rows": int(len(df)),
        "date_min": df["date"].min().date().isoformat(),
        "date_max": df["date"].max().date().isoformat(),
        "price_min_low": float(df["low"].min()),
        "price_max_high": float(df["high"].max()),
        "close_min": float(df["close"].min()),
        "close_max": float(df["close"].max()),
        "volume_min": int(df["volume"].min()),
        "volume_max": int(df["volume"].max()),
        "duplicate_dates": dup_count,
        "ohlc_bad_count": int(len(ohlc_bad)),
        "huge_return_count": int(len(huge_return)),
        "huge_range_count": int(len(huge_range)),
        "volume_spike_count": int(len(vol_spike)),
        "business_day_missing_count": int(len(missing_bdays)),
        "ohlc_bad_dates": [d.date().isoformat() for d in ohlc_bad["date"].head(20)],
        "huge_return_dates": [d.date().isoformat() for d in huge_return["date"].head(20)],
        "huge_range_dates": [d.date().isoformat() for d in huge_range["date"].head(20)],
        "volume_spike_dates": [d.date().isoformat() for d in vol_spike["date"].head(20)],
    }


def fetch_pykrx(start: str, end: str) -> tuple[pd.DataFrame | None, str | None]:
    try:
        from pykrx import stock
        ext = stock.get_market_ohlcv_by_date(start, end, STOCK_CODE)
        if ext is None or ext.empty:
            return None, "pykrx returned empty dataframe"
        ext = ext.reset_index().rename(columns={
            "날짜": "date",
            "시가": "ext_open",
            "고가": "ext_high",
            "저가": "ext_low",
            "종가": "ext_close",
            "거래량": "ext_volume",
        })
        ext["date"] = pd.to_datetime(ext["date"])
        keep = [c for c in ["date", "ext_open", "ext_high", "ext_low", "ext_close", "ext_volume"] if c in ext.columns]
        return ext[keep], None
    except Exception as exc:
        return None, f"pykrx fetch failed: {type(exc).__name__}: {exc}"


def compare_external(df: pd.DataFrame) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    start = df["date"].min().strftime("%Y%m%d")
    end = df["date"].max().strftime("%Y%m%d")
    ext, error = fetch_pykrx(start, end)
    if ext is None:
        return None, {"external_source": "pykrx/KRX", "available": False, "error": error}
    cmp = df.merge(ext, on="date", how="inner")
    if cmp.empty:
        return cmp, {"external_source": "pykrx/KRX", "available": False, "error": "no overlapping dates"}
    cmp["close_diff"] = cmp["close"] - cmp["ext_close"]
    cmp["close_ratio"] = cmp["close"] / cmp["ext_close"].replace(0, pd.NA)
    cmp["close_diff_pct"] = (cmp["close_diff"] / cmp["ext_close"].replace(0, pd.NA)) * 100
    rounded_ratio = cmp["close_ratio"].dropna().round(4)
    mode_ratio = float(rounded_ratio.mode().iloc[0]) if not rounded_ratio.empty else math.nan
    median_ratio = float(cmp["close_ratio"].median())
    max_abs_diff_pct = float(cmp["close_diff_pct"].abs().max())
    latest = cmp.sort_values("date").iloc[-1]
    summary = {
        "external_source": "pykrx/KRX",
        "available": True,
        "overlap_rows": int(len(cmp)),
        "median_close_ratio": median_ratio,
        "mode_close_ratio_rounded4": mode_ratio,
        "max_abs_diff_pct": max_abs_diff_pct,
        "latest_date": latest["date"].date().isoformat(),
        "latest_kiwoom_close": float(latest["close"]),
        "latest_external_close": float(latest["ext_close"]),
        "latest_ratio": float(latest["close_ratio"]),
    }
    return cmp, summary


def build_chart(df: pd.DataFrame, cmp: pd.DataFrame | None) -> tuple[Path, Path | None]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    plot_df = df.copy()
    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.46, 0.16, 0.13, 0.13, 0.12],
        subplot_titles=(
            "삼성전자 Kiwoom 일봉 OHLC + MA/BB",
            "거래량 + Volume MA20",
            "RSI14",
            "MACD",
            "외부 KRX 종가 비교 비율 / 일별 수익률",
        ),
    )
    fig.add_trace(go.Candlestick(
        x=plot_df["date"], open=plot_df["open"], high=plot_df["high"], low=plot_df["low"], close=plot_df["close"],
        name="Kiwoom OHLC",
        increasing_line_color="#16a34a", decreasing_line_color="#dc2626",
    ), row=1, col=1)
    for col, color in [("ma5", "#f59e0b"), ("ma20", "#2563eb"), ("ma60", "#7c3aed"), ("bb_upper", "#94a3b8"), ("bb_lower", "#94a3b8")]:
        fig.add_trace(go.Scatter(x=plot_df["date"], y=plot_df[col], name=col.upper(), mode="lines", line=dict(width=1.4, color=color)), row=1, col=1)
    fig.add_trace(go.Bar(x=plot_df["date"], y=plot_df["volume"], name="Volume", marker_color="#64748b"), row=2, col=1)
    fig.add_trace(go.Scatter(x=plot_df["date"], y=plot_df["vol_ma20"], name="Vol MA20", mode="lines", line=dict(color="#f97316")), row=2, col=1)
    fig.add_trace(go.Scatter(x=plot_df["date"], y=plot_df["rsi14"], name="RSI14", mode="lines", line=dict(color="#0ea5e9")), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#ef4444", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#22c55e", row=3, col=1)
    fig.add_trace(go.Scatter(x=plot_df["date"], y=plot_df["macd"], name="MACD", mode="lines", line=dict(color="#2563eb")), row=4, col=1)
    fig.add_trace(go.Scatter(x=plot_df["date"], y=plot_df["macd_signal"], name="Signal", mode="lines", line=dict(color="#f97316")), row=4, col=1)
    fig.add_trace(go.Bar(x=plot_df["date"], y=plot_df["macd_hist"], name="Hist", marker_color="#94a3b8"), row=4, col=1)
    fig.add_trace(go.Scatter(x=plot_df["date"], y=plot_df["daily_return_pct"], name="Daily return %", mode="lines", line=dict(color="#a855f7")), row=5, col=1)
    if cmp is not None and not cmp.empty and "close_ratio" in cmp:
        fig.add_trace(go.Scatter(x=cmp["date"], y=cmp["close_ratio"], name="Kiwoom/KRX close ratio", mode="lines", line=dict(color="#ef4444", width=2)), row=5, col=1)
        fig.add_hline(y=1.0, line_dash="dash", line_color="#334155", row=5, col=1)
    fig.update_layout(
        template="plotly_white",
        title=f"{STOCK_CODE} {STOCK_NAME} 데이터 검증 대시보드 — Kiwoom vs KRX",
        height=1200,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=30, t=80, b=40),
    )
    html_path = REPORT_DIR / "samsung_validation_dashboard.html"
    fig.write_html(html_path, include_plotlyjs="cdn")
    png_path = REPORT_DIR / "samsung_validation_dashboard.png"
    try:
        fig.write_image(png_path, width=1600, height=1200, scale=2)
        return html_path, png_path
    except Exception:
        return html_path, None


def verdict(quality: dict[str, Any], external: dict[str, Any]) -> tuple[str, list[str]]:
    issues: list[str] = []
    if quality["duplicate_dates"]:
        issues.append(f"중복 날짜 {quality['duplicate_dates']}개")
    if quality["ohlc_bad_count"]:
        issues.append(f"OHLC 구조 오류 {quality['ohlc_bad_count']}개")
    if quality["huge_return_count"]:
        issues.append(f"절대 일수익률 30% 초과 {quality['huge_return_count']}개")
    if not external.get("available"):
        issues.append(f"외부 KRX 비교 실패: {external.get('error')}")
    else:
        ratio = float(external["median_close_ratio"])
        maxdiff = float(external["max_abs_diff_pct"])
        # For a tradable price series, ratio should be close to 1. A constant 5x/10x still means scaling problem.
        if abs(ratio - 1.0) > 0.01 or maxdiff > 1.0:
            issues.append(f"Kiwoom/KRX 종가 불일치: median_ratio={ratio:.6f}, max_abs_diff_pct={maxdiff:.2f}%")
    if issues:
        return "비정상: 가격 스케일/데이터 소스 검증 후 재수집 필요. 50종목 지표 계산과 신호 생성을 보류합니다.", issues
    return "정상: 삼성전자 기준 데이터 품질과 외부 가격 비교 통과. 50종목 지표 계산 진행 가능.", []


def write_report(df: pd.DataFrame, quality: dict[str, Any], external: dict[str, Any], final_verdict: str, issues: list[str], html_path: Path, png_path: Path | None, cmp_path: Path | None) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    latest = df.sort_values("date").tail(5)[["date", "open", "high", "low", "close", "volume"]].copy()
    latest["date"] = latest["date"].dt.date.astype(str)
    lines = []
    lines.append(f"# 삼성전자 데이터 검증 리포트\n")
    lines.append(f"- 종목: `{STOCK_CODE} {STOCK_NAME}`")
    lines.append(f"- DB source: `{SOURCE}`")
    lines.append(f"- 차트: `{html_path}`")
    if png_path:
        lines.append(f"- PNG: `{png_path}`")
    if cmp_path:
        lines.append(f"- 외부 비교 CSV: `{cmp_path}`")
    lines.append("\n## 1. DB 데이터 품질 요약\n")
    for k in ["rows", "date_min", "date_max", "price_min_low", "price_max_high", "close_min", "close_max", "volume_min", "volume_max", "duplicate_dates", "ohlc_bad_count", "huge_return_count", "huge_range_count", "volume_spike_count", "business_day_missing_count"]:
        lines.append(f"- {k}: `{quality[k]}`")
    lines.append("\n## 2. 최근 5개 일봉\n")
    lines.append(latest.to_markdown(index=False))
    lines.append("\n## 3. 외부 KRX 비교\n")
    lines.append("```json")
    lines.append(json.dumps(external, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("\n## 4. 판정\n")
    lines.append(f"**{final_verdict}**")
    if issues:
        lines.append("\n### 발견 이슈")
        for item in issues:
            lines.append(f"- {item}")
    lines.append("\n## 5. 다음 액션\n")
    if issues:
        lines.append("- `TRADING_ENV=mock` 데이터와 KRX 실제 가격이 불일치하는지 확인합니다.")
        lines.append("- 동일 `ka10081`을 `prod` 환경으로 재수집 가능한지 확인 후 삼성전자 1종목부터 재검증합니다.")
        lines.append("- 정상 판정 전에는 50종목 지표 계산 및 신호 생성을 보류합니다.")
    else:
        lines.append("- 50종목 전체 technical_indicators 계산을 진행합니다.")
        lines.append("- 이후 trading_signals를 생성하고 신호 차트를 재검증합니다.")
    report_path = REPORT_DIR / "samsung_validation_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    env = load_env()
    if not env.get("DATABASE_URL"):
        print("❌ DATABASE_URL missing", file=sys.stderr)
        return 2
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = add_indicators(read_kiwoom_df(env["DATABASE_URL"]))
    quality = quality_checks(df)
    cmp, external = compare_external(df)
    cmp_path: Path | None = None
    if cmp is not None and not cmp.empty:
        cmp_path = REPORT_DIR / "samsung_kiwoom_vs_krx_comparison.csv"
        cmp.to_csv(cmp_path, index=False, encoding="utf-8-sig")
    html_path, png_path = build_chart(df, cmp)
    final_verdict, issues = verdict(quality, external)
    report_path = write_report(df, quality, external, final_verdict, issues, html_path, png_path, cmp_path)
    print("검증 완료")
    print(f"report={report_path}")
    print(f"html={html_path}")
    print(f"png={png_path if png_path else 'PNG 생성 실패/생략'}")
    print(f"comparison_csv={cmp_path if cmp_path else '없음'}")
    print(f"verdict={final_verdict}")
    if issues:
        print("issues:")
        for i in issues:
            print(f"- {i}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
