"""Analyze a daily-signal to minute-entry/exit scenario using real DB data.

Example:
- daily signal date: 2026-05-22
- minute entry at 10:00
- no intraday exit until 15:00/15:20/time horizon

This script can analyze hypothetical daily signals even if trading_signals does not
contain that exact signal, but it labels the signal_source accordingly.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import psycopg

from core.supabase_rest import read_env  # noqa: E402

KST = timezone(timedelta(hours=9))


def parse_date_for_daily(day: str) -> str:
    return day.replace("-", "")


def compact_day(value: Any) -> str:
    text = str(value)
    return text[:10].replace("-", "")


def iso_day(value: Any) -> str:
    compact = compact_day(value)
    return f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"


def row_to_minute(ts: datetime, o: Any, h: Any, l: Any, c: Any, v: Any) -> dict[str, Any]:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    kst = ts.astimezone(KST)
    return {
        "ts": kst,
        "time": kst.strftime("%H:%M"),
        "open": float(o),
        "high": float(h),
        "low": float(l),
        "close": float(c),
        "volume": float(v or 0),
    }


def return_pct(entry: float, price: float) -> float:
    return round((price - entry) / entry * 100.0, 4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-code", default="005930")
    parser.add_argument("--daily-signal-date", required=True, help="YYYY-MM-DD or YYYYMMDD")
    parser.add_argument("--entry-date", default=None, help="YYYY-MM-DD. Defaults to daily signal date.")
    parser.add_argument("--entry-time", default="10:00")
    parser.add_argument("--exit-check-time", default="15:00")
    parser.add_argument("--time-exit", default="15:20")
    parser.add_argument("--max-holding-days", type=int, default=3)
    parser.add_argument("--stop-loss-pct", type=float, default=-2.0)
    parser.add_argument("--take-profit-pct", type=float, default=5.0)
    args = parser.parse_args()

    signal_day = args.daily_signal_date.replace("-", "")
    entry_day = (args.entry_date or args.daily_signal_date).replace("-", "")
    env = read_env(PROJECT_ROOT / ".env")
    blocks: list[str] = []
    alerts: list[str] = []

    out: dict[str, Any] = {
        "ok": True,
        "stage": "analyze_daily_to_minute_signal_scenario",
        "stock_code": args.stock_code,
        "scenario": {
            "daily_signal_date": signal_day,
            "entry_day": entry_day,
            "entry_time": args.entry_time,
            "exit_check_time": args.exit_check_time,
            "time_exit": args.time_exit,
            "max_holding_days": args.max_holding_days,
            "stop_loss_pct": args.stop_loss_pct,
            "take_profit_pct": args.take_profit_pct,
        },
    }

    with psycopg.connect(env["DATABASE_URL"], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select date, open, high, low, close, volume, source
                from daily_prices
                where stock_code=%s and date >= %s
                order by date asc
                limit %s
                """,
                (args.stock_code, signal_day, args.max_holding_days + 5),
            )
            daily_rows = [
                dict(zip(["date", "open", "high", "low", "close", "volume", "source"], row))
                for row in cur.fetchall()
            ]
            cur.execute(
                """
                select signal_date, signal_type, score, price, strategy, reason
                from trading_signals
                where stock_code=%s and signal_date::date=%s::date
                order by signal_date desc
                """,
                (args.stock_code, f"{signal_day[:4]}-{signal_day[4:6]}-{signal_day[6:8]}"),
            )
            signals = [
                dict(zip(["signal_date", "signal_type", "score", "price", "strategy", "reason"], row))
                for row in cur.fetchall()
            ]
            minute_by_day: dict[str, list[dict[str, Any]]] = {}
            for d in [r["date"] for r in daily_rows[: args.max_holding_days + 1]]:
                day_iso = iso_day(d)
                cur.execute(
                    """
                    select timestamp, open, high, low, close, volume
                    from intraday_prices
                    where stock_code=%s and source='kiwoom_ka10080_minute' and time_frame='1min'
                      and (timestamp at time zone 'Asia/Seoul')::date=%s::date
                    order by timestamp asc
                    """,
                    (args.stock_code, day_iso),
                )
                minute_by_day[compact_day(d)] = [row_to_minute(*row) for row in cur.fetchall()]

    entry_rows = minute_by_day.get(entry_day, [])
    entry_bar = next((r for r in entry_rows if r["time"] == args.entry_time), None)
    if entry_bar is None:
        blocks.append("entry_bar_missing")
        out["ok"] = False
        out["blocking_conditions"] = blocks
        out["daily_rows"] = daily_rows
        out["signals"] = signals
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 2

    entry_price = entry_bar["close"]
    exit_events: list[dict[str, Any]] = []
    per_day: list[dict[str, Any]] = []
    first_exit: dict[str, Any] | None = None
    holding_index = 0
    for daily in daily_rows:
        day = compact_day(daily["date"])
        rows = minute_by_day.get(day, [])
        if not rows:
            per_day.append({"date": day, "minute_rows": 0, "data_quality": "missing_minute_data"})
            continue
        day_rows = rows
        if day == entry_day:
            day_rows = [r for r in rows if r["time"] >= args.entry_time]
        if not day_rows:
            continue
        day_high = max(r["high"] for r in day_rows)
        day_low = min(r["low"] for r in day_rows)
        close_1530 = next((r["close"] for r in rows if r["time"] == "15:30"), rows[-1]["close"])
        check_bar = next((r for r in rows if r["time"] == args.exit_check_time), None)
        summary = {
            "date": day,
            "minute_rows": len(rows),
            "first_minute": rows[0]["time"],
            "last_minute": rows[-1]["time"],
            "high_after_entry_or_day": day_high,
            "low_after_entry_or_day": day_low,
            "return_to_day_high_pct": return_pct(entry_price, day_high),
            "return_to_day_low_pct": return_pct(entry_price, day_low),
            "close_1530": close_1530,
            "return_to_1530_pct": return_pct(entry_price, close_1530),
            "exit_check_time": args.exit_check_time,
            "exit_check_price": check_bar["close"] if check_bar else None,
            "return_to_exit_check_pct": return_pct(entry_price, check_bar["close"]) if check_bar else None,
        }
        per_day.append(summary)

        for r in day_rows:
            ret_low = return_pct(entry_price, r["low"])
            ret_high = return_pct(entry_price, r["high"])
            if first_exit is None and ret_low <= args.stop_loss_pct:
                first_exit = {
                    "exit_type": "STOP_LOSS_SIGNAL",
                    "date": day,
                    "time": r["time"],
                    "threshold_pct": args.stop_loss_pct,
                    "estimated_exit_price": round(entry_price * (1 + args.stop_loss_pct / 100.0), 2),
                    "return_pct": args.stop_loss_pct,
                }
                break
            if first_exit is None and ret_high >= args.take_profit_pct:
                first_exit = {
                    "exit_type": "TAKE_PROFIT_SIGNAL",
                    "date": day,
                    "time": r["time"],
                    "threshold_pct": args.take_profit_pct,
                    "estimated_exit_price": round(entry_price * (1 + args.take_profit_pct / 100.0), 2),
                    "return_pct": args.take_profit_pct,
                }
                break
            if first_exit is None and r["time"] >= args.time_exit and day == daily_rows[min(args.max_holding_days, len(daily_rows)-1)]["date"]:
                first_exit = {
                    "exit_type": "TIME_EXIT_SIGNAL",
                    "date": day,
                    "time": r["time"],
                    "estimated_exit_price": r["close"],
                    "return_pct": return_pct(entry_price, r["close"]),
                }
                break
        if first_exit:
            break
        holding_index += 1
        if holding_index >= args.max_holding_days:
            break

    out.update(
        {
            "signal_source": "stored_trading_signals" if signals else "hypothetical_daily_signal",
            "stored_signals": signals,
            "daily_rows": daily_rows,
            "entry": {
                "date": entry_day,
                "time": args.entry_time,
                "price": entry_price,
                "bar": entry_bar,
            },
            "per_day_outcome": per_day,
            "first_exit_signal": first_exit,
            "blocking_conditions": blocks,
            "alerts": alerts,
        }
    )
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
