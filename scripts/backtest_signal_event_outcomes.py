"""Backtest stored daily trading signals into auditable signal_events.

This implements the saved signal-utilization reports:
- DAILY_ENTRY_CANDIDATE for stored BUY signals
- EXIT_SIGNAL for stored SELL signals
- BLOCKED_ENTRY_SIGNAL when OR10/OR30 has no valid entry or missing data
- INTRADAY_ENTRY_SIGNAL when OR10/OR30 breakout entry exists
- outcome JSON with after_1d/3d daily returns and intraday OR trade result

Safety:
- Uses only real Supabase/Postgres rows from trading_signals, daily_prices, intraday_prices.
- Does not call Kiwoom order APIs.
- Does not write orders/positions.
- Writes only signal_events when --record-events is passed.
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

import psycopg
from psycopg.types.json import Jsonb

from core.supabase_rest import read_env  # noqa: E402

KST = timezone(timedelta(hours=9))


@dataclass
class MinuteBar:
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


def as_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(KST).date() if value.tzinfo else value.date()
    return datetime.fromisoformat(str(value)[:10]).date()


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


def ensure_signal_events_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            create table if not exists signal_events (
                id bigserial primary key,
                event_key text not null unique,
                event_time timestamptz not null,
                trading_date date,
                stock_code varchar(20) not null,
                event_type varchar(64) not null,
                strategy varchar(128),
                source_signal_id bigint,
                source_signal_type varchar(32),
                source_signal_score numeric,
                signal_price numeric,
                reference_price numeric,
                system_action varchar(64),
                human_action varchar(64),
                blocking_conditions jsonb not null default '[]'::jsonb,
                score_details jsonb not null default '{}'::jsonb,
                outcome jsonb not null default '{}'::jsonb,
                metadata jsonb not null default '{}'::jsonb,
                created_at timestamptz not null default now()
            )
            """
        )
        cur.execute("create index if not exists idx_signal_events_stock_date on signal_events(stock_code, trading_date)")
        cur.execute("create index if not exists idx_signal_events_type_date on signal_events(event_type, trading_date)")
        cur.execute("create index if not exists idx_signal_events_source_signal on signal_events(source_signal_id)")
    conn.commit()


def latest_signal_date(cur: psycopg.Cursor) -> date | None:
    cur.execute("select max(signal_date::date) from trading_signals")
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def fetch_signals(cur: psycopg.Cursor, signal_day: date, limit: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        select id, stock_code, signal_type, signal_date, time_frame, price, price_at_signal,
               score, signal_strength, score_details, reason, strategy, executed
        from trading_signals
        where signal_date::date = %s
        order by
          case signal_type when 'BUY' then 0 when 'SELL' then 1 else 2 end,
          coalesce(score, signal_strength, 0) desc,
          stock_code asc
        limit %s
        """,
        (signal_day, limit),
    )
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_daily_rows(cur: psycopg.Cursor, stock_code: str, start_day: date, days: int = 8) -> list[dict[str, Any]]:
    cur.execute(
        """
        select date, open, high, low, close, volume, source
        from daily_prices
        where stock_code=%s and date >= %s
        order by date asc
        limit %s
        """,
        (stock_code, start_day, days),
    )
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def next_minute_trading_day(cur: psycopg.Cursor, stock_code: str, signal_day: date) -> date | None:
    """Return the next KST trading day available in ka10080 minute rows."""
    cur.execute(
        """
        select min((timestamp at time zone 'Asia/Seoul')::date)
        from intraday_prices
        where stock_code=%s
          and source='kiwoom_ka10080_minute'
          and time_frame='1min'
          and (timestamp at time zone 'Asia/Seoul')::date > %s
        """,
        (stock_code, signal_day),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def fetch_minute_bars(cur: psycopg.Cursor, stock_code: str, trading_day: date) -> list[MinuteBar]:
    cur.execute(
        """
        select timestamp, open, high, low, close, volume
        from intraday_prices
        where stock_code=%s
          and source='kiwoom_ka10080_minute'
          and time_frame='1min'
          and (timestamp at time zone 'Asia/Seoul')::date=%s
        order by timestamp asc
        """,
        (stock_code, trading_day),
    )
    out: list[MinuteBar] = []
    for ts, o, h, l, c, v in cur.fetchall():
        kst = ts_to_kst(ts)
        out.append(MinuteBar(kst, kst.strftime("%H:%M"), num(o), num(h), num(l), num(c), int(v or 0)))
    return out


def daily_outcome(signal: dict[str, Any], daily_rows: list[dict[str, Any]]) -> dict[str, Any]:
    signal_price = num(signal.get("price") or signal.get("price_at_signal"))
    if not signal_price and daily_rows:
        signal_price = num(daily_rows[0].get("close"))
    out: dict[str, Any] = {
        "reference_price": signal_price or None,
        "daily_rows_available": len(daily_rows),
    }
    if not signal_price:
        out["blocking_conditions"] = ["signal_reference_price_missing"]
        return out
    for idx, label in [(0, "signal_day"), (1, "after_1d"), (3, "after_3d")]:
        if len(daily_rows) > idx:
            row = daily_rows[idx]
            close = num(row.get("close"))
            high = num(row.get("high"))
            low = num(row.get("low"))
            out[label] = {
                "date": str(row.get("date")),
                "close": close,
                "return_close_pct": pct(signal_price, close),
                "return_high_pct": pct(signal_price, high),
                "return_low_pct": pct(signal_price, low),
            }
    return out


def simulate_or_entry(
    bars: list[MinuteBar],
    window_minutes: int,
    *,
    fee_bps_one_way: float,
    slippage_bps_one_way: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    time_exit: str,
) -> dict[str, Any]:
    range_end = "09:10" if window_minutes == 10 else "09:30"
    range_bars = [b for b in bars if "09:00" <= b.hhmm <= range_end]
    entry_candidates = [b for b in bars if b.hhmm > range_end]
    expected_count = window_minutes + 1
    have_minutes = {b.hhmm for b in range_bars}
    if len(have_minutes) < expected_count:
        return {
            "ok": False,
            "blocking_conditions": ["opening_range_minutes_incomplete"],
            "range_end": range_end,
            "expected_minutes": expected_count,
            "actual_minutes": len(have_minutes),
        }
    opening_high = max(b.high for b in range_bars)
    opening_low = min(b.low for b in range_bars)
    entry_idx = None
    entry_bar = None
    for idx, bar in enumerate(entry_candidates):
        if bar.high > opening_high:
            entry_idx = idx
            entry_bar = bar
            break
    if entry_bar is None or entry_idx is None:
        proxy_start = range_bars[-1].close if range_bars else 0.0
        proxy_exit_bar = next((b for b in entry_candidates if b.hhmm >= time_exit), None) or (entry_candidates[-1] if entry_candidates else (bars[-1] if bars else None))
        proxy_exit = proxy_exit_bar.close if proxy_exit_bar else 0.0
        post_range = entry_candidates or []
        return {
            "ok": False,
            "blocking_conditions": ["no_opening_range_breakout"],
            "range_end": range_end,
            "opening_high": opening_high,
            "opening_low": opening_low,
            "blocked_proxy_start_price": proxy_start or None,
            "blocked_proxy_exit_time": proxy_exit_bar.hhmm if proxy_exit_bar else None,
            "blocked_proxy_exit_price": proxy_exit or None,
            "blocked_proxy_return_to_time_exit_pct": pct(proxy_start, proxy_exit) if proxy_start and proxy_exit else None,
            "blocked_proxy_return_to_day_high_pct": pct(proxy_start, max((b.high for b in post_range), default=0.0)) if proxy_start and post_range else None,
            "blocked_proxy_return_to_day_low_pct": pct(proxy_start, min((b.low for b in post_range), default=0.0)) if proxy_start and post_range else None,
        }

    entry_price = entry_bar.close
    exit_price = None
    exit_time = None
    exit_reason = "time_exit_or_last_close"
    for bar in entry_candidates[entry_idx + 1 :]:
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
    gross = pct(entry_price, exit_price)
    cost_pct = ((fee_bps_one_way + slippage_bps_one_way) / 100.0) * 2
    net = round((gross or 0.0) - cost_pct, 4)
    return {
        "ok": True,
        "blocking_conditions": [],
        "range_end": range_end,
        "opening_high": opening_high,
        "opening_low": opening_low,
        "entry_time": entry_bar.hhmm,
        "entry_price": entry_price,
        "exit_time": exit_time,
        "exit_price": round(exit_price, 4),
        "exit_reason": exit_reason,
        "gross_return_pct": gross,
        "cost_pct": round(cost_pct, 4),
        "net_return_pct": net,
    }


def build_events_for_signal(
    cur: psycopg.Cursor,
    signal: dict[str, Any],
    *,
    fee_bps_one_way: float,
    slippage_bps_one_way: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    time_exit: str,
) -> list[dict[str, Any]]:
    signal_id = int(signal["id"])
    stock_code = str(signal["stock_code"])
    signal_type = str(signal["signal_type"])
    signal_dt = ts_to_kst(signal["signal_date"])
    signal_day = signal_dt.date()
    score = num(signal.get("score") or signal.get("signal_strength"))
    signal_price = num(signal.get("price") or signal.get("price_at_signal")) or None
    score_details = signal.get("score_details") or {}
    if not isinstance(score_details, dict):
        score_details = {"raw": score_details}

    daily_rows = fetch_daily_rows(cur, stock_code, signal_day, 8)
    d_out = daily_outcome(signal, daily_rows)
    ref_price = d_out.get("reference_price")

    base_type = {
        "BUY": "DAILY_ENTRY_CANDIDATE",
        "SELL": "EXIT_SIGNAL",
        "HOLD": "DAILY_HOLD_SIGNAL",
    }.get(signal_type, "DAILY_SIGNAL")
    system_action = {
        "BUY": "WATCH_ONLY",
        "SELL": "AVOID_OR_EXIT_CANDIDATE",
        "HOLD": "NO_ACTION",
    }.get(signal_type, "NO_ACTION")
    events: list[dict[str, Any]] = [
        {
            "event_key": f"daily:{base_type}:{signal_id}",
            "event_time": signal["signal_date"],
            "trading_date": signal_day,
            "stock_code": stock_code,
            "event_type": base_type,
            "strategy": signal.get("strategy") or "technical_score_v1",
            "source_signal_id": signal_id,
            "source_signal_type": signal_type,
            "source_signal_score": score,
            "signal_price": signal_price,
            "reference_price": ref_price,
            "system_action": system_action,
            "human_action": "NOT_ENTERED" if signal_type == "BUY" else "NOT_APPLICABLE",
            "blocking_conditions": d_out.get("blocking_conditions") or [],
            "score_details": score_details,
            "outcome": d_out,
            "metadata": {"reason": signal.get("reason"), "time_frame": signal.get("time_frame")},
        }
    ]

    if signal_type != "BUY":
        return events

    next_trade_day = next_minute_trading_day(cur, stock_code, signal_day)
    # If no next-day minute rows exist yet, fall back to the next daily row only for
    # older historical signals. Never reuse the same signal day for a post-close
    # daily BUY signal, because that would let the backtest enter before the signal
    # actually existed.
    if next_trade_day is None and len(daily_rows) >= 2:
        candidate_day = as_date(daily_rows[1]["date"])
        if candidate_day > signal_day:
            next_trade_day = candidate_day
    if next_trade_day is None:
        events.append(
            {
                **events[0],
                "event_key": f"or:blocked:no_next_trading_day:{signal_id}",
                "event_type": "BLOCKED_ENTRY_SIGNAL",
                "system_action": "BLOCKED",
                "blocking_conditions": ["next_trading_day_missing"],
                "outcome": {"blocking_conditions": ["next_trading_day_missing"], "daily_signal_outcome": d_out},
                "metadata": {"variant": "OR_UNAVAILABLE"},
            }
        )
        return events

    bars = fetch_minute_bars(cur, stock_code, next_trade_day)
    if not bars:
        events.append(
            {
                **events[0],
                "event_key": f"or:blocked:minute_missing:{signal_id}:{next_trade_day}",
                "event_time": datetime.combine(next_trade_day, datetime.min.time(), tzinfo=KST),
                "trading_date": next_trade_day,
                "event_type": "BLOCKED_ENTRY_SIGNAL",
                "system_action": "BLOCKED",
                "blocking_conditions": ["minute_data_missing_for_next_trading_day"],
                "outcome": {"minute_rows": 0, "blocking_conditions": ["minute_data_missing_for_next_trading_day"], "daily_signal_outcome": d_out},
                "metadata": {"variant": "OR_UNAVAILABLE", "entry_trading_date": str(next_trade_day)},
            }
        )
        return events

    for window in (10, 30):
        or_result = simulate_or_entry(
            bars,
            window,
            fee_bps_one_way=fee_bps_one_way,
            slippage_bps_one_way=slippage_bps_one_way,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            time_exit=time_exit,
        )
        variant = f"OR{window}"
        event_type = "INTRADAY_ENTRY_SIGNAL" if or_result.get("ok") else "BLOCKED_ENTRY_SIGNAL"
        events.append(
            {
                **events[0],
                "event_key": f"or:{variant}:{event_type}:{signal_id}:{next_trade_day}",
                "event_time": datetime.combine(next_trade_day, datetime.min.time(), tzinfo=KST),
                "trading_date": next_trade_day,
                "event_type": event_type,
                "strategy": f"shigeru_intraday_{variant.lower()}_v1",
                "reference_price": or_result.get("entry_price") or ref_price,
                "system_action": "WATCH_ONLY" if event_type == "INTRADAY_ENTRY_SIGNAL" else "BLOCKED",
                "human_action": "NOT_ENTERED",
                "blocking_conditions": or_result.get("blocking_conditions") or [],
                "outcome": {"intraday": or_result, "daily_signal_outcome": d_out},
                "metadata": {
                    "variant": variant,
                    "entry_trading_date": str(next_trade_day),
                    "minute_rows": len(bars),
                    "source": "kiwoom_ka10080_minute",
                    "time_frame": "1min",
                },
            }
        )
    return events


def delete_existing_events_for_signals(cur: psycopg.Cursor, signal_ids: list[int]) -> int:
    if not signal_ids:
        return 0
    cur.execute("delete from signal_events where source_signal_id = any(%s)", (signal_ids,))
    return cur.rowcount or 0


def upsert_events(cur: psycopg.Cursor, events: list[dict[str, Any]]) -> None:
    for e in events:
        cur.execute(
            """
            insert into signal_events (
              event_key, event_time, trading_date, stock_code, event_type, strategy,
              source_signal_id, source_signal_type, source_signal_score, signal_price,
              reference_price, system_action, human_action, blocking_conditions,
              score_details, outcome, metadata
            ) values (
              %(event_key)s, %(event_time)s, %(trading_date)s, %(stock_code)s, %(event_type)s, %(strategy)s,
              %(source_signal_id)s, %(source_signal_type)s, %(source_signal_score)s, %(signal_price)s,
              %(reference_price)s, %(system_action)s, %(human_action)s, %(blocking_conditions)s,
              %(score_details)s, %(outcome)s, %(metadata)s
            )
            on conflict (event_key) do update set
              event_time=excluded.event_time,
              trading_date=excluded.trading_date,
              strategy=excluded.strategy,
              source_signal_score=excluded.source_signal_score,
              signal_price=excluded.signal_price,
              reference_price=excluded.reference_price,
              system_action=excluded.system_action,
              human_action=excluded.human_action,
              blocking_conditions=excluded.blocking_conditions,
              score_details=excluded.score_details,
              outcome=excluded.outcome,
              metadata=excluded.metadata
            """,
            {
                **e,
                "blocking_conditions": Jsonb(e.get("blocking_conditions") or []),
                "score_details": Jsonb(e.get("score_details") or {}),
                "outcome": Jsonb(e.get("outcome") or {}),
                "metadata": Jsonb(e.get("metadata") or {}),
            },
        )


def aggregate(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_type = Counter(e["event_type"] for e in events)
    intraday_returns: dict[str, list[float]] = defaultdict(list)
    blocks = Counter()
    daily_buy_1d: list[float] = []
    daily_buy_3d: list[float] = []
    sell_1d: list[float] = []
    sell_3d: list[float] = []
    for e in events:
        for b in e.get("blocking_conditions") or []:
            blocks[str(b)] += 1
        outcome = e.get("outcome") or {}
        if e["event_type"] == "INTRADAY_ENTRY_SIGNAL":
            variant = (e.get("metadata") or {}).get("variant", "unknown")
            ret = (((outcome.get("intraday") or {}).get("net_return_pct")))
            if ret is not None:
                intraday_returns[str(variant)].append(float(ret))
        if e["event_type"] in {"DAILY_ENTRY_CANDIDATE", "EXIT_SIGNAL", "DAILY_HOLD_SIGNAL"}:
            r1 = ((outcome.get("after_1d") or {}).get("return_close_pct"))
            r3 = ((outcome.get("after_3d") or {}).get("return_close_pct"))
            if e["event_type"] == "DAILY_ENTRY_CANDIDATE":
                if r1 is not None: daily_buy_1d.append(float(r1))
                if r3 is not None: daily_buy_3d.append(float(r3))
            if e["event_type"] == "EXIT_SIGNAL":
                if r1 is not None: sell_1d.append(float(r1))
                if r3 is not None: sell_3d.append(float(r3))

    def ret_summary(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"count": 0, "avg_pct": None, "positive_rate_pct": None, "min_pct": None, "max_pct": None}
        pos = sum(1 for v in values if v > 0)
        return {
            "count": len(values),
            "avg_pct": round(sum(values) / len(values), 4),
            "positive_rate_pct": round(pos / len(values) * 100.0, 2),
            "min_pct": round(min(values), 4),
            "max_pct": round(max(values), 4),
        }

    return {
        "event_type_counts": dict(by_type),
        "blocking_condition_counts": dict(blocks),
        "daily_buy_after_1d": ret_summary(daily_buy_1d),
        "daily_buy_after_3d": ret_summary(daily_buy_3d),
        "sell_signal_after_1d": ret_summary(sell_1d),
        "sell_signal_after_3d": ret_summary(sell_3d),
        "intraday_or_returns": {k: ret_summary(v) for k, v in sorted(intraday_returns.items())},
    }


def write_markdown_report(path: Path, data: dict[str, Any]) -> None:
    summary = data["summary"]
    lines = [
        "# 신호 이벤트 활용 백테스트 리포트",
        "",
        f"- 생성 시각: `{data['generated_at']}`",
        f"- 대상 signal_date: `{data['signal_date']}`",
        f"- 대상 신호 수: `{data['signal_count']}`",
        f"- record_events: `{data['record_events']}`",
        "- 안전 상태: 주문/포지션 미변경, signal_events만 선택적으로 upsert",
        "",
        "## 이벤트 카운트",
        "",
        "| event_type | count |",
        "|---|---:|",
    ]
    for k, v in sorted(summary["event_type_counts"].items()):
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Daily BUY 이후 수익률", "", "| horizon | count | avg_pct | positive_rate_pct | min | max |", "|---|---:|---:|---:|---:|---:|"]
    for label, key in [("after_1d", "daily_buy_after_1d"), ("after_3d", "daily_buy_after_3d")]:
        s = summary[key]
        lines.append(f"| {label} | {s['count']} | {s['avg_pct']} | {s['positive_rate_pct']} | {s['min_pct']} | {s['max_pct']} |")
    lines += ["", "## SELL 신호 이후 수익률", "", "| horizon | count | avg_pct | positive_rate_pct | min | max |", "|---|---:|---:|---:|---:|---:|"]
    for label, key in [("after_1d", "sell_signal_after_1d"), ("after_3d", "sell_signal_after_3d")]:
        s = summary[key]
        lines.append(f"| {label} | {s['count']} | {s['avg_pct']} | {s['positive_rate_pct']} | {s['min_pct']} | {s['max_pct']} |")
    lines += ["", "## OR 분봉 진입 백테스트", "", "| variant | count | avg_pct | positive_rate_pct | min | max |", "|---|---:|---:|---:|---:|---:|"]
    for variant, s in sorted(summary["intraday_or_returns"].items()):
        lines.append(f"| {variant} | {s['count']} | {s['avg_pct']} | {s['positive_rate_pct']} | {s['min_pct']} | {s['max_pct']} |")
    lines += ["", "## 차단 조건", "", "| blocking_condition | count |", "|---|---:|"]
    for k, v in sorted(summary["blocking_condition_counts"].items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "## 운영 판단",
        "",
        "- 이 리포트는 저장된 일봉 신호를 실제 일봉/ka10080 1분봉 데이터로 replay한 것입니다.",
        "- 평균 수익률/차단 조건을 근거로 신호 활용층을 개선하되, 실주문 executor는 구현하지 않았습니다.",
        "- paper/real 전환은 별도 성과 게이트 통과 전까지 계속 금지입니다.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signal-date", help="YYYY-MM-DD. Defaults to latest trading_signals signal_date::date")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--record-events", action="store_true", help="Upsert generated events into signal_events table")
    parser.add_argument("--keep-existing-events", action="store_true", help="Do not delete existing signal_events for the same source_signal_id before upsert")
    parser.add_argument("--fee-bps", type=float, default=23.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--stop-loss-pct", type=float, default=-1.0)
    parser.add_argument("--take-profit-pct", type=float, default=1.5)
    parser.add_argument("--time-exit", default="15:20")
    parser.add_argument("--json-out", default="reports/signal_event_outcomes_latest.json")
    parser.add_argument("--md-out", default="reports/signal_event_outcomes_latest.md")
    args = parser.parse_args()

    env = read_env(PROJECT_ROOT / ".env")
    if not env.get("DATABASE_URL"):
        out = {"ok": False, "status": "blocked", "blocking_conditions": ["missing_database_url"]}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    all_events: list[dict[str, Any]] = []
    with psycopg.connect(env["DATABASE_URL"], connect_timeout=20, prepare_threshold=None) as conn:
        ensure_signal_events_table(conn)
        with conn.cursor() as cur:
            signal_day = datetime.fromisoformat(args.signal_date).date() if args.signal_date else latest_signal_date(cur)
            if signal_day is None:
                out = {"ok": False, "status": "blocked", "blocking_conditions": ["no_trading_signals"]}
                print(json.dumps(out, ensure_ascii=False, indent=2))
                return 2
            signals = fetch_signals(cur, signal_day, args.limit)
            if not signals:
                out = {"ok": False, "status": "blocked", "signal_date": str(signal_day), "blocking_conditions": ["no_signals_for_date"]}
                print(json.dumps(out, ensure_ascii=False, indent=2))
                return 2
            for sig in signals:
                all_events.extend(
                    build_events_for_signal(
                        cur,
                        sig,
                        fee_bps_one_way=args.fee_bps,
                        slippage_bps_one_way=args.slippage_bps,
                        stop_loss_pct=args.stop_loss_pct,
                        take_profit_pct=args.take_profit_pct,
                        time_exit=args.time_exit,
                    )
                )
            deleted_existing_events = 0
            if args.record_events:
                if not args.keep_existing_events:
                    deleted_existing_events = delete_existing_events_for_signals(cur, [int(s["id"]) for s in signals])
                upsert_events(cur, all_events)
                conn.commit()

    data = {
        "ok": True,
        "stage": "backtest_signal_event_outcomes",
        "status": "completed",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "signal_date": str(signal_day),
        "signal_count": len(signals),
        "event_count": len(all_events),
        "record_events": args.record_events,
        "deleted_existing_events": deleted_existing_events,
        "summary": aggregate(all_events),
        "events": all_events[:500],
        "blocking_conditions": [],
        "alerts": [],
        "next_actions": [
            "BLOCKED_ENTRY_SIGNAL의 차단 조건별 이후 수익률을 비교해 opening layer가 과도 차단인지 판단하세요.",
            "INTRADAY_ENTRY_SIGNAL 평균 수익률이 음수면 paper/real 전환 금지를 유지하세요.",
            "성과 개선은 threshold/weight 변경 전 리포트 기반으로 검토하세요.",
        ],
    }
    json_path = PROJECT_ROOT / args.json_out
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_markdown_report(PROJECT_ROOT / args.md_out, data)
    printable = {k: v for k, v in data.items() if k != "events"}
    printable["json_out"] = str(json_path)
    printable["md_out"] = str(PROJECT_ROOT / args.md_out)
    print(json.dumps(printable, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
