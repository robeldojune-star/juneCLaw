"""Create static PNG charts for Fujimoto 1-2-6 backtest trades.

Reads a backtest JSON artifact, fetches real ka10080 1-minute bars from
Supabase/Postgres, and plots candles + entry/exit markers for visual QA.
Read-only except writing PNG files.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import read_env  # noqa: E402

SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"
KST = timezone(timedelta(hours=9))


def num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def ts_to_kst(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


def parse_day(text: str) -> date:
    return datetime.fromisoformat(text[:10]).date()


def fetch_bars(cur: Any, stock_code: str, trading_day: date) -> list[dict[str, Any]]:
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
    out: list[dict[str, Any]] = []
    for ts, o, h, l, c, v in cur.fetchall():
        kst = ts_to_kst(ts)
        out.append({"ts": kst, "hhmm": kst.strftime("%H:%M"), "open": num(o), "high": num(h), "low": num(l), "close": num(c), "volume": int(v or 0)})
    return out


def moving_average(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for idx in range(len(values)):
        if idx + 1 < window:
            out.append(None)
        else:
            out.append(sum(values[idx + 1 - window : idx + 1]) / window)
    return out


def plot_trade(row: dict[str, Any], bars: list[dict[str, Any]], out_path: Path) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    x = list(range(len(bars)))
    closes = [bar["close"] for bar in bars]
    ma5 = moving_average(closes, 5)
    ma20 = moving_average(closes, 20)
    entry_time = row.get("entry_time")
    exit_time = row.get("exit_time")
    entry_idx = next((idx for idx, bar in enumerate(bars) if bar["hhmm"] == entry_time), None)
    exit_idx = next((idx for idx, bar in enumerate(bars) if bar["hhmm"] == exit_time), None)

    fig, (ax, axv) = plt.subplots(2, 1, figsize=(16, 9), sharex=True, gridspec_kw={"height_ratios": [4, 1]})
    fig.patch.set_facecolor("#111827")
    ax.set_facecolor("#111827")
    axv.set_facecolor("#111827")

    width = 0.65
    for idx, bar in enumerate(bars):
        up = bar["close"] >= bar["open"]
        color = "#ef4444" if up else "#3b82f6"  # Korean app convention: up red, down blue
        ax.vlines(idx, bar["low"], bar["high"], color=color, linewidth=0.8, alpha=0.9)
        low_body = min(bar["open"], bar["close"])
        height = max(abs(bar["close"] - bar["open"]), 0.01)
        ax.add_patch(Rectangle((idx - width / 2, low_body), width, height, facecolor=color, edgecolor=color, alpha=0.85))
        axv.bar(idx, bar["volume"], color=color, width=0.8, alpha=0.65)

    ax.plot(x, [v if v is not None else float("nan") for v in ma5], color="#facc15", linewidth=1.2, label="MA5")
    ax.plot(x, [v if v is not None else float("nan") for v in ma20], color="#22c55e", linewidth=1.2, label="MA20")

    if entry_idx is not None:
        ax.scatter([entry_idx], [row.get("entry_price") or bars[entry_idx]["close"]], s=130, marker="^", color="#22c55e", edgecolor="white", zorder=5, label="ENTRY")
        ax.axvline(entry_idx, color="#22c55e", linestyle="--", linewidth=1.0, alpha=0.8)
    if exit_idx is not None:
        ax.scatter([exit_idx], [row.get("exit_price") or bars[exit_idx]["close"]], s=130, marker="v", color="#f97316", edgecolor="white", zorder=5, label="EXIT")
        ax.axvline(exit_idx, color="#f97316", linestyle="--", linewidth=1.0, alpha=0.8)

    title = f"Fujimoto 1-2-6 | {row.get('stock_code')} {row.get('entry_trading_date') or row.get('trading_day')} | net={row.get('net_return_pct')}% | {row.get('exit_reason')}"
    ax.set_title(title, color="white", fontsize=14)
    ax.grid(True, color="#374151", linewidth=0.5, alpha=0.5)
    axv.grid(True, color="#374151", linewidth=0.5, alpha=0.4)
    ax.tick_params(colors="#d1d5db")
    axv.tick_params(colors="#d1d5db")
    for spine in [*ax.spines.values(), *axv.spines.values()]:
        spine.set_color("#4b5563")
    ax.legend(loc="upper left")

    tick_step = max(1, len(bars) // 12)
    ticks = x[::tick_step]
    axv.set_xticks(ticks)
    axv.set_xticklabels([bars[idx]["hhmm"] for idx in ticks], rotation=45, ha="right", color="#d1d5db")
    axv.set_ylabel("Volume", color="#d1d5db")
    ax.set_ylabel("Price", color="#d1d5db")

    blocks = ", ".join(row.get("blocking_conditions", [])[:4])
    fig.text(0.01, 0.01, f"blocks: {blocks} | read-only, paper/real blocked", color="#d1d5db", fontsize=9)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.03, 1, 0.98))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-in", default="reports/fujimoto_126_backtest_signals_full.json")
    parser.add_argument("--out-dir", default="reports/fujimoto_126_charts")
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()

    json_path = PROJECT_ROOT / args.json_in
    data = json.loads(json_path.read_text(encoding="utf-8"))
    candidates = [row for row in data.get("results", []) if row.get("ok")]
    candidates.sort(key=lambda row: (row.get("net_return_pct") is not None, float(row.get("net_return_pct") or -999)), reverse=True)

    env = read_env(PROJECT_ROOT / ".env")
    if not env.get("DATABASE_URL"):
        print(json.dumps({"ok": False, "blocking_conditions": ["missing_database_url"]}, ensure_ascii=False, indent=2))
        return 2

    import psycopg

    outputs: list[str] = []
    with psycopg.connect(env["DATABASE_URL"], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            for row in candidates[: args.limit]:
                day_text = row.get("entry_trading_date") or row.get("trading_day")
                code = str(row.get("stock_code"))
                if not day_text or not code:
                    continue
                bars = fetch_bars(cur, code, parse_day(str(day_text)))
                if not bars:
                    continue
                safe = f"{day_text}_{code}_{row.get('entry_time','noentry').replace(':','')}_{row.get('net_return_pct')}".replace("/", "_")
                out_path = PROJECT_ROOT / args.out_dir / f"fujimoto_126_{safe}.png"
                plot_trade(row, bars, out_path)
                outputs.append(str(out_path))

    print(json.dumps({"ok": True, "json_in": str(json_path), "chart_count": len(outputs), "charts": outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
