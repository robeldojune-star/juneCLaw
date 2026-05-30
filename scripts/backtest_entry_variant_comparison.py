"""Compare opening-entry variants using stored daily BUY signals and ka10080 minute bars.

Variants implemented without changing production strategy thresholds/order logic:
- immediate_breakout: enter first bar after OR range whose high breaks opening high.
- pullback_rebreak: after first breakout, require pullback to opening_high or below,
  then enter on rebreak above opening_high.
- entry_window: immediate breakout but only until --entry-end (default 10:00).
- volume_confirmed_breakout: immediate breakout with breakout volume >= opening range
  average volume * --volume-multiplier.
- early_drop_filtered_breakout: immediate breakout, but reject entries that suffer a
  fast adverse move within --early-drop-minutes.
- ten_oclock_confirmation: enter at/after 10:00 only if close is above opening high.

Safety: read-only except report files. No orders/positions, no Kiwoom order APIs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import read_env  # noqa: E402

KST = timezone(timedelta(hours=9))
VARIANTS = [
    "immediate_breakout",
    "pullback_rebreak",
    "entry_window",
    "volume_confirmed_breakout",
    "early_drop_filtered_breakout",
    "ten_oclock_confirmation",
]


@dataclass(frozen=True)
class Bar:
    ts: datetime
    hhmm: str
    open: float
    high: float
    low: float
    close: float
    volume: int


def num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def pct(base: float, value: float) -> float | None:
    if not base:
        return None
    return round((value - base) / base * 100.0, 4)


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


def ret_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "avg_pct": None, "positive_rate_pct": None, "min_pct": None, "max_pct": None}
    positive = sum(1 for value in values if value > 0)
    return {
        "count": len(values),
        "avg_pct": round(sum(values) / len(values), 4),
        "positive_rate_pct": round(positive / len(values) * 100.0, 2),
        "min_pct": round(min(values), 4),
        "max_pct": round(max(values), 4),
    }


def split_opening_range(bars: list[Bar], window_minutes: int) -> tuple[str, list[Bar], list[Bar]]:
    range_end = "09:10" if window_minutes == 10 else "09:30"
    range_bars = [bar for bar in bars if "09:00" <= bar.hhmm <= range_end]
    candidates = [bar for bar in bars if bar.hhmm > range_end]
    return range_end, range_bars, candidates


def opening_range_stats(bars: list[Bar], window_minutes: int) -> tuple[dict[str, Any], list[Bar], list[Bar]]:
    range_end, range_bars, candidates = split_opening_range(bars, window_minutes)
    expected = window_minutes + 1
    have = {bar.hhmm for bar in range_bars}
    if len(have) < expected:
        return (
            {
                "ok": False,
                "range_end": range_end,
                "blocking_conditions": ["opening_range_minutes_incomplete"],
                "expected_minutes": expected,
                "actual_minutes": len(have),
            },
            range_bars,
            candidates,
        )
    return (
        {
            "ok": True,
            "range_end": range_end,
            "opening_high": max(bar.high for bar in range_bars),
            "opening_low": min(bar.low for bar in range_bars),
            "opening_avg_volume": sum(bar.volume for bar in range_bars) / len(range_bars),
        },
        range_bars,
        candidates,
    )


def _entry_result(bar: Bar, stats: dict[str, Any], variant: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "variant": variant,
        "entry_time": bar.hhmm,
        "entry_price": bar.close,
        "opening_high": stats.get("opening_high"),
        "opening_low": stats.get("opening_low"),
        "range_end": stats.get("range_end"),
        "blocking_conditions": [],
        **(extra or {}),
    }


def simulate_entry_variant(
    bars: list[Bar],
    *,
    variant: str,
    window_minutes: int,
    entry_end: str = "10:00",
    volume_multiplier: float = 1.5,
    early_drop_minutes: int = 5,
    early_drop_pct: float = -0.7,
    confirm_time: str = "10:00",
) -> dict[str, Any]:
    stats, range_bars, candidates = opening_range_stats(bars, window_minutes)
    if not stats.get("ok"):
        return {**stats, "variant": variant}
    opening_high = float(stats["opening_high"])
    opening_avg_volume = float(stats["opening_avg_volume"])

    if variant == "immediate_breakout":
        for bar in candidates:
            if bar.high > opening_high:
                return _entry_result(bar, stats, variant)
        return {**stats, "ok": False, "variant": variant, "blocking_conditions": ["no_opening_range_breakout"]}

    if variant == "entry_window":
        for bar in candidates:
            if bar.hhmm > entry_end:
                break
            if bar.high > opening_high:
                return _entry_result(bar, stats, variant, {"entry_end": entry_end})
        return {**stats, "ok": False, "variant": variant, "blocking_conditions": ["no_breakout_inside_entry_window"], "entry_end": entry_end}

    if variant == "volume_confirmed_breakout":
        saw_breakout = False
        threshold = opening_avg_volume * volume_multiplier
        for bar in candidates:
            if bar.high > opening_high:
                saw_breakout = True
                if bar.volume >= threshold:
                    return _entry_result(bar, stats, variant, {"volume_threshold": threshold, "breakout_volume": bar.volume})
        reason = "breakout_volume_below_threshold" if saw_breakout else "no_opening_range_breakout"
        return {**stats, "ok": False, "variant": variant, "blocking_conditions": [reason], "volume_threshold": threshold}

    if variant == "early_drop_filtered_breakout":
        for idx, bar in enumerate(candidates):
            if bar.high > opening_high:
                watch = candidates[idx + 1 : idx + 1 + max(0, early_drop_minutes)]
                threshold_price = bar.close * (1 + early_drop_pct / 100.0)
                if any(next_bar.low <= threshold_price for next_bar in watch):
                    return {
                        **stats,
                        "ok": False,
                        "variant": variant,
                        "blocking_conditions": ["early_drop_filter_triggered"],
                        "candidate_entry_time": bar.hhmm,
                        "candidate_entry_price": bar.close,
                        "early_drop_minutes": early_drop_minutes,
                        "early_drop_pct": early_drop_pct,
                    }
                return _entry_result(bar, stats, variant, {"early_drop_minutes": early_drop_minutes, "early_drop_pct": early_drop_pct})
        return {**stats, "ok": False, "variant": variant, "blocking_conditions": ["no_opening_range_breakout"]}

    if variant == "pullback_rebreak":
        broke = False
        pulled_back = False
        for bar in candidates:
            if not broke:
                if bar.high > opening_high:
                    broke = True
                continue
            if broke and not pulled_back:
                if bar.low <= opening_high:
                    pulled_back = True
                continue
            if pulled_back and bar.high > opening_high:
                return _entry_result(bar, stats, variant)
        reason = "no_initial_breakout" if not broke else ("no_pullback_after_breakout" if not pulled_back else "no_rebreak_after_pullback")
        return {**stats, "ok": False, "variant": variant, "blocking_conditions": [reason]}

    if variant == "ten_oclock_confirmation":
        for bar in candidates:
            if bar.hhmm >= confirm_time:
                if bar.close > opening_high:
                    return _entry_result(bar, stats, variant, {"confirm_time": confirm_time})
                return {**stats, "ok": False, "variant": variant, "blocking_conditions": ["ten_oclock_close_not_above_opening_high"], "confirm_time": confirm_time, "confirm_close": bar.close}
        return {**stats, "ok": False, "variant": variant, "blocking_conditions": ["confirm_bar_missing"], "confirm_time": confirm_time}

    return {"ok": False, "variant": variant, "blocking_conditions": [f"unknown_variant:{variant}"]}


def simulate_exit(
    bars: list[Bar],
    entry_time: str,
    entry_price: float,
    *,
    stop_loss_pct: float,
    take_profit_pct: float,
    time_exit: str,
    fee_bps: float,
    slippage_bps: float,
) -> dict[str, Any]:
    post = [bar for bar in bars if bar.hhmm > entry_time]
    exit_price = None
    exit_time = None
    exit_reason = "last_close_exit"
    for bar in post:
        low_ret = (bar.low - entry_price) / entry_price * 100.0
        high_ret = (bar.high - entry_price) / entry_price * 100.0
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
    if exit_price is None:
        last = bars[-1]
        exit_price = last.close
        exit_time = last.hhmm
    gross = pct(entry_price, exit_price) or 0.0
    cost = ((fee_bps + slippage_bps) / 100.0) * 2
    return {
        "exit_time": exit_time,
        "exit_price": round(exit_price, 4),
        "exit_reason": exit_reason,
        "gross_return_pct": round(gross, 4),
        "cost_pct": round(cost, 4),
        "net_return_pct": round(gross - cost, 4),
    }


def simulate_trade_variant(
    bars: list[Bar],
    *,
    variant: str,
    window_minutes: int,
    entry_end: str,
    volume_multiplier: float,
    early_drop_minutes: int,
    early_drop_pct: float,
    confirm_time: str,
    stop_loss_pct: float,
    take_profit_pct: float,
    time_exit: str,
    fee_bps: float,
    slippage_bps: float,
) -> dict[str, Any]:
    entry = simulate_entry_variant(
        bars,
        variant=variant,
        window_minutes=window_minutes,
        entry_end=entry_end,
        volume_multiplier=volume_multiplier,
        early_drop_minutes=early_drop_minutes,
        early_drop_pct=early_drop_pct,
        confirm_time=confirm_time,
    )
    if not entry.get("ok"):
        return entry
    exit_result = simulate_exit(
        bars,
        str(entry["entry_time"]),
        float(entry["entry_price"]),
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        time_exit=time_exit,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
    )
    return {**entry, **exit_result}


def fetch_signal_dates(cur: Any, start: date | None, end: date | None) -> list[date]:
    params: list[Any] = []
    where = ["signal_type='BUY'"]
    if start:
        where.append("signal_date::date >= %s")
        params.append(start)
    if end:
        where.append("signal_date::date <= %s")
        params.append(end)
    cur.execute(f"select distinct signal_date::date from trading_signals where {' and '.join(where)} order by 1", params)
    return [row[0] for row in cur.fetchall()]


def fetch_buy_signals(cur: Any, signal_day: date, limit: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        select id, stock_code, signal_date, price, price_at_signal, score, signal_strength, strategy
        from trading_signals
        where signal_type='BUY' and signal_date::date=%s
        order by coalesce(score, signal_strength, 0) desc, stock_code asc
        limit %s
        """,
        (signal_day, limit),
    )
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def next_minute_trading_day(cur: Any, stock_code: str, signal_day: date) -> date | None:
    cur.execute(
        """
        select min((timestamp at time zone 'Asia/Seoul')::date)
        from intraday_prices
        where stock_code=%s and source='kiwoom_ka10080_minute' and time_frame='1min'
          and (timestamp at time zone 'Asia/Seoul')::date > %s
        """,
        (stock_code, signal_day),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def fetch_bars(cur: Any, stock_code: str, trading_day: date) -> list[Bar]:
    cur.execute(
        """
        select timestamp, open, high, low, close, volume
        from intraday_prices
        where stock_code=%s and source='kiwoom_ka10080_minute' and time_frame='1min'
          and (timestamp at time zone 'Asia/Seoul')::date=%s
        order by timestamp asc
        """,
        (stock_code, trading_day),
    )
    out: list[Bar] = []
    for ts, o, h, l, c, v in cur.fetchall():
        kst = ts_to_kst(ts)
        out.append(Bar(kst, kst.strftime("%H:%M"), num(o), num(h), num(l), num(c), int(v or 0)))
    return out


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[(str(row["variant"]), int(row["window_minutes"]))].append(row)
    variants = {}
    for (variant, window), rows in sorted(grouped.items()):
        entries = [row for row in rows if row.get("ok")]
        rets = [float(row["net_return_pct"]) for row in entries if row.get("net_return_pct") is not None]
        blocks = Counter(reason for row in rows if not row.get("ok") for reason in row.get("blocking_conditions", []))
        exits = Counter(str(row.get("exit_reason")) for row in entries if row.get("exit_reason"))
        variants[f"{variant}_OR{window}"] = {
            "signals_seen": len(rows),
            "entries": len(entries),
            "entry_rate_pct": round(len(entries) / len(rows) * 100.0, 2) if rows else None,
            "returns": ret_summary(rets),
            "exit_reason_counts": dict(exits),
            "blocking_condition_counts": dict(blocks),
        }
    ranked = sorted(
        ((name, data) for name, data in variants.items()),
        key=lambda item: (item[1]["returns"]["avg_pct"] is not None, item[1]["returns"]["avg_pct"] or -999, item[1]["entries"]),
        reverse=True,
    )
    return {"variants": variants, "ranking_by_avg_return": [{"variant": name, **data} for name, data in ranked]}


def write_markdown(path: Path, data: dict[str, Any]) -> None:
    lines = [
        "# OR 진입 변형 비교 백테스트",
        "",
        f"- 생성 시각: `{data['generated_at']}`",
        f"- 대상 signal_dates: `{', '.join(data['signal_dates'])}`",
        f"- BUY 신호 수: `{data['buy_signal_count']}`",
        f"- 실제 평가 rows: `{data['evaluated_result_count']}`",
        "- 안전 상태: read-only 백테스트, 주문/포지션 미변경",
        "",
        "## 변형별 성과",
        "",
        "| variant | signals_seen | entries | entry_rate | avg_net | positive_rate | min | max | exits | blocks |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for name, stats in data["summary"]["variants"].items():
        ret = stats["returns"]
        lines.append(
            f"| {name} | {stats['signals_seen']} | {stats['entries']} | {stats['entry_rate_pct']} | "
            f"{ret['avg_pct']} | {ret['positive_rate_pct']} | {ret['min_pct']} | {ret['max_pct']} | "
            f"`{json.dumps(stats['exit_reason_counts'], ensure_ascii=False)}` | "
            f"`{json.dumps(stats['blocking_condition_counts'], ensure_ascii=False)}` |"
        )
    lines += ["", "## 순위(avg_net 기준)", ""]
    for idx, row in enumerate(data["summary"]["ranking_by_avg_return"], 1):
        lines.append(f"{idx}. `{row['variant']}` avg={row['returns']['avg_pct']} entries={row['entries']} positive={row['returns']['positive_rate_pct']}")
    lines += ["", "## 운영 판단", "", *[f"- {item}" for item in data.get("interpretation", [])], ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_day(text: str | None) -> date | None:
    return datetime.fromisoformat(text[:10]).date() if text else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--limit-per-date", type=int, default=50)
    parser.add_argument("--windows", nargs="+", type=int, default=[10, 30])
    parser.add_argument("--entry-end", default="10:00")
    parser.add_argument("--volume-multiplier", type=float, default=1.5)
    parser.add_argument("--early-drop-minutes", type=int, default=5)
    parser.add_argument("--early-drop-pct", type=float, default=-0.7)
    parser.add_argument("--confirm-time", default="10:00")
    parser.add_argument("--stop-loss-pct", type=float, default=-1.0)
    parser.add_argument("--take-profit-pct", type=float, default=1.5)
    parser.add_argument("--time-exit", default="15:20")
    parser.add_argument("--fee-bps", type=float, default=23.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--json-out", default="reports/entry_variant_comparison_latest.json")
    parser.add_argument("--md-out", default="reports/entry_variant_comparison_latest.md")
    args = parser.parse_args()

    env = read_env(PROJECT_ROOT / ".env")
    if not env.get("DATABASE_URL"):
        print(json.dumps({"ok": False, "blocking_conditions": ["missing_database_url"]}, ensure_ascii=False, indent=2))
        return 2

    import psycopg

    results: list[dict[str, Any]] = []
    signals_seen = 0
    missing_next_day = 0
    with psycopg.connect(env["DATABASE_URL"], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            signal_dates = fetch_signal_dates(cur, parse_day(args.start_date), parse_day(args.end_date))
            for signal_day in signal_dates:
                signals = fetch_buy_signals(cur, signal_day, args.limit_per_date)
                signals_seen += len(signals)
                for sig in signals:
                    code = str(sig["stock_code"])
                    next_day = next_minute_trading_day(cur, code, signal_day)
                    if next_day is None:
                        missing_next_day += 1
                        continue
                    bars = fetch_bars(cur, code, next_day)
                    if not bars:
                        missing_next_day += 1
                        continue
                    for window in args.windows:
                        for variant in VARIANTS:
                            outcome = simulate_trade_variant(
                                bars,
                                variant=variant,
                                window_minutes=window,
                                entry_end=args.entry_end,
                                volume_multiplier=args.volume_multiplier,
                                early_drop_minutes=args.early_drop_minutes,
                                early_drop_pct=args.early_drop_pct,
                                confirm_time=args.confirm_time,
                                stop_loss_pct=args.stop_loss_pct,
                                take_profit_pct=args.take_profit_pct,
                                time_exit=args.time_exit,
                                fee_bps=args.fee_bps,
                                slippage_bps=args.slippage_bps,
                            )
                            results.append(
                                {
                                    "signal_date": str(signal_day),
                                    "entry_trading_date": str(next_day),
                                    "source_signal_id": sig["id"],
                                    "stock_code": code,
                                    "signal_score": num(sig.get("score") or sig.get("signal_strength")),
                                    "window_minutes": window,
                                    **outcome,
                                }
                            )

    summary = aggregate(results)
    interpretation = []
    if len(signal_dates) <= 1:
        interpretation.append("현재 trading_signals의 signal_date가 1개라 표본이 작습니다.")
    if missing_next_day:
        interpretation.append(f"다음 거래일 ka10080 분봉 누락 BUY 신호가 {missing_next_day}건입니다.")
    best = summary["ranking_by_avg_return"][0] if summary["ranking_by_avg_return"] else None
    if best:
        interpretation.append(f"현재 표본의 avg_net 1위는 {best['variant']}입니다(avg={best['returns']['avg_pct']}, entries={best['entries']}).")
    interpretation.append("paper/real 주문 전환은 이 비교만으로 하지 말고, 과거 signal_date/ka10080 표본 확대한 뒤 판단하세요.")

    data = {
        "ok": True,
        "stage": "entry_variant_comparison",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "signal_dates": [str(d) for d in signal_dates],
        "buy_signal_count": signals_seen,
        "missing_next_day_minute_count": missing_next_day,
        "evaluated_result_count": len(results),
        "parameters": vars(args),
        "summary": summary,
        "results": results,
        "interpretation": interpretation,
        "blocking_conditions": [],
        "alerts": [] if len(signal_dates) > 1 else ["only_one_signal_date_available_in_trading_signals"],
    }
    json_path = PROJECT_ROOT / args.json_out
    md_path = PROJECT_ROOT / args.md_out
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_markdown(md_path, data)
    printable = {k: v for k, v in data.items() if k != "results"}
    printable["json_out"] = str(json_path)
    printable["md_out"] = str(md_path)
    print(json.dumps(printable, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
