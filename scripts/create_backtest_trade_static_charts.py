"""Create static PNG charts for opening backtest trades.

Uses matplotlib so WebUI can render images directly without Plotly/CDN.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from core.supabase_rest import SupabaseRestClient, SupabaseRestError, num  # noqa: E402

SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"
KST = timezone(timedelta(hours=9))


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


def fetch_rows(sb: SupabaseRestClient, stock_code: str, days: int) -> list[dict[str, Any]]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = sb.get(
            "intraday_prices",
            {
                "select": "stock_code,timestamp,time_frame,source,open,high,low,close,volume,trading_value",
                "stock_code": f"eq.{stock_code}",
                "time_frame": f"eq.{TIME_FRAME}",
                "source": f"eq.{SOURCE}",
                "timestamp": f"gte.{since}",
                "order": "timestamp.asc",
                "limit": "1000",
                "offset": str(offset),
            },
            timeout=60,
        )
        rows.extend(page)
        if len(page) < 1000:
            break
        offset += 1000
    return rows


def minute_range(start_hhmm: str, end_hhmm: str) -> set[str]:
    base = "2026-01-01"
    cur = datetime.fromisoformat(f"{base}T{start_hhmm}:00+09:00")
    end = datetime.fromisoformat(f"{base}T{end_hhmm}:00+09:00")
    out: set[str] = set()
    while cur <= end:
        out.add(cur.strftime("%H:%M"))
        cur = cur.replace(minute=cur.minute + 1) if cur.minute < 59 else cur.replace(hour=cur.hour + 1, minute=0)
    return out


def group_by_day(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ts = parse_ts(row.get("timestamp"))
        if ts is None:
            continue
        row = dict(row)
        row["_ts_kst"] = ts
        row["_time_kst"] = ts.strftime("%H:%M")
        row["_date_kst"] = ts.strftime("%Y-%m-%d")
        by_day[row["_date_kst"]].append(row)
    for day in by_day:
        by_day[day].sort(key=lambda r: r["_ts_kst"])
    return dict(by_day)


def eligible(day_rows: list[dict[str, Any]]) -> bool:
    return not (minute_range("09:00", "09:30") - {str(r.get("_time_kst")) for r in day_rows})


def simulate(day_rows: list[dict[str, Any]], fee_bps: float, slippage_bps: float, *, window: int = 10) -> dict[str, Any] | None:
    if len(day_rows) < 3:
        return None
    range_end = "09:10" if window == 10 else "09:30"
    range_rows = [r for r in day_rows if "09:00" <= str(r.get("_time_kst")) <= range_end]
    entry_candidates = [r for r in day_rows if str(r.get("_time_kst")) > range_end]
    expected = window + 1
    if len({str(r.get("_time_kst")) for r in range_rows}) < expected:
        return None
    opening_high = max(num(r.get("high")) for r in range_rows)
    if opening_high <= 0:
        return None
    entry = None
    for row in entry_candidates:
        if num(row.get("high")) > opening_high:
            entry = row
            break
    if entry is None:
        return None
    exit_row = day_rows[-1]
    entry_price = num(entry.get("close"))
    exit_price = num(exit_row.get("close"))
    if entry_price <= 0 or exit_price <= 0:
        return None
    gross = (exit_price - entry_price) / entry_price * 100
    cost = (fee_bps + slippage_bps) / 100 * 2
    return {
        "stock_code": entry.get("stock_code"),
        "date": entry.get("_date_kst"),
        "or_window": f"OR{window}",
        "range_end": range_end,
        "opening_high": opening_high,
        "entry_ts": entry["_ts_kst"],
        "entry_time": entry["_time_kst"],
        "entry_price": entry_price,
        "exit_ts": exit_row["_ts_kst"],
        "exit_time": exit_row["_time_kst"],
        "exit_price": exit_price,
        "gross_return_pct": round(gross, 4),
        "cost_pct": round(cost, 4),
        "net_return_pct": round(gross - cost, 4),
    }


def draw_candle(ax, rows: list[dict[str, Any]]) -> None:
    width = 0.00042  # roughly 0.6 minute in matplotlib date units
    for row in rows:
        ts = mdates.date2num(row["_ts_kst"].replace(tzinfo=None))
        o, h, l, c = num(row.get("open")), num(row.get("high")), num(row.get("low")), num(row.get("close"))
        color = "#d62728" if c >= o else "#1f77b4"  # Korean style: red up, blue down
        ax.vlines(ts, l, h, color=color, linewidth=0.7, alpha=0.9)
        low = min(o, c)
        height = max(abs(c - o), 1)
        ax.add_patch(Rectangle((ts - width / 2, low), width, height, facecolor=color, edgecolor=color, linewidth=0.5, alpha=0.85))


def create_chart(rows: list[dict[str, Any]], trade: dict[str, Any], out_path: Path) -> None:
    times = [r["_ts_kst"].replace(tzinfo=None) for r in rows]
    closes = [num(r.get("close")) for r in rows]
    vols = [num(r.get("volume")) for r in rows]
    fig, (ax, axv) = plt.subplots(2, 1, figsize=(16, 9), gridspec_kw={"height_ratios": [4, 1]}, sharex=True)
    fig.patch.set_facecolor("#0b1020")
    for a in (ax, axv):
        a.set_facecolor("#111827")
        a.tick_params(colors="#e5e7eb")
        for spine in a.spines.values():
            spine.set_color("#334155")
        a.grid(True, color="#1f2937", linewidth=0.5)

    draw_candle(ax, rows)
    ax.plot(times, closes, color="#facc15", linewidth=0.8, alpha=0.45, label="Close")
    ax.axhline(trade["opening_high"], color="#facc15", linestyle="--", linewidth=1.2, label=f"{trade['or_window']} range high")
    ax.axvspan(datetime.fromisoformat(f"{trade['date']}T09:00:00"), datetime.fromisoformat(f"{trade['date']}T{trade['range_end']}:00"), color="#2563eb", alpha=0.10, label=f"09:00~{trade['range_end']} range window")
    ax.scatter([trade["entry_ts"].replace(tzinfo=None)], [trade["entry_price"]], marker="^", s=180, color="#22c55e", edgecolor="white", zorder=5, label="ENTRY/SIGNAL")
    ax.scatter([trade["exit_ts"].replace(tzinfo=None)], [trade["exit_price"]], marker="v", s=180, color="#f97316", edgecolor="white", zorder=5, label="EXIT")
    ax.annotate(f"ENTRY {trade['entry_time']}\n{trade['entry_price']:,.0f}", xy=(trade["entry_ts"].replace(tzinfo=None), trade["entry_price"]), xytext=(12, 24), textcoords="offset points", color="#86efac", arrowprops={"arrowstyle":"->", "color":"#86efac"})
    ax.annotate(f"EXIT {trade['exit_time']}\n{trade['exit_price']:,.0f}", xy=(trade["exit_ts"].replace(tzinfo=None), trade["exit_price"]), xytext=(-90, -40), textcoords="offset points", color="#fdba74", arrowprops={"arrowstyle":"->", "color":"#fdba74"})
    ret_color = "#86efac" if trade["net_return_pct"] > 0 else "#fca5a5"
    ax.set_title(f"{trade['stock_code']} {trade['date']} | signal={trade['entry_time']} exit={trade['exit_time']} net={trade['net_return_pct']:.4f}%", color=ret_color, fontsize=15)
    ax.legend(loc="upper left", facecolor="#111827", edgecolor="#334155", labelcolor="#e5e7eb")

    axv.bar(times, vols, width=0.0005, color="#64748b", alpha=0.7)
    axv.set_ylabel("Volume", color="#e5e7eb")
    axv.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-codes", nargs="+", default=["005930", "000660", "035420", "005380", "068270"])
    parser.add_argument("--days", type=int, default=130)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--window", type=int, choices=[10, 30], default=10)
    parser.add_argument("--fee-bps", type=float, default=23.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--out-dir", default="reports/backtest_trade_charts_static")
    args = parser.parse_args()

    out_dir = PROJECT_ROOT / args.out_dir
    trades: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    blocks: list[str] = []
    try:
        sb = SupabaseRestClient()
        for code in args.stock_codes:
            for _day, rows in group_by_day(fetch_rows(sb, code, args.days)).items():
                if not eligible(rows):
                    continue
                trade = simulate(rows, args.fee_bps, args.slippage_bps, window=args.window)
                if trade:
                    trades.append((trade, rows))
    except SupabaseRestError as exc:
        blocks.append(str(exc))

    trades.sort(key=lambda x: (str(x[0]["date"]), str(x[0]["stock_code"])))
    created = []
    for trade, rows in trades[: max(0, args.limit)]:
        path = out_dir / f"{trade['date']}_{trade['stock_code']}_{trade['or_window']}_entry_exit.png"
        create_chart(rows, trade, path)
        created.append({
            "stock_code": trade["stock_code"],
            "date": trade["date"],
            "entry_time": trade["entry_time"],
            "exit_time": trade["exit_time"],
            "net_return_pct": trade["net_return_pct"],
            "path": str(path),
        })
    print(json.dumps({"ok": not blocks, "created": created, "blocking_conditions": blocks}, ensure_ascii=False, indent=2))
    return 0 if not blocks else 2


if __name__ == "__main__":
    raise SystemExit(main())
