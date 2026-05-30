"""Batch replay signal_events for multiple signal_date values and compare outcomes.

Purpose:
- Run the single-day signal event backtest for every stored trading_signals date
  in a range.
- Upsert signal_events idempotently when --record-events is passed.
- Produce cumulative JSON/Markdown reports.
- Compare BLOCKED_ENTRY_SIGNAL vs INTRADAY_ENTRY_SIGNAL outcomes.

Safety:
- Uses only real Supabase/Postgres data.
- Does not write orders/positions and does not call Kiwoom order APIs.
- Writes only signal_events when --record-events is enabled.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import psycopg

from core.supabase_rest import read_env  # noqa: E402
from scripts import backtest_signal_event_outcomes as single  # noqa: E402


def parse_day(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.fromisoformat(value[:10]).date()


def ret_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "avg_pct": None,
            "positive_rate_pct": None,
            "min_pct": None,
            "max_pct": None,
        }
    positive = sum(1 for value in values if value > 0)
    return {
        "count": len(values),
        "avg_pct": round(sum(values) / len(values), 4),
        "positive_rate_pct": round(positive / len(values) * 100.0, 2),
        "min_pct": round(min(values), 4),
        "max_pct": round(max(values), 4),
    }


def fetch_signal_dates(cur: psycopg.Cursor, start: date | None, end: date | None, max_dates: int | None) -> list[date]:
    params: list[Any] = []
    where: list[str] = []
    if start:
        where.append("signal_date::date >= %s")
        params.append(start)
    if end:
        where.append("signal_date::date <= %s")
        params.append(end)
    sql = "select distinct signal_date::date as d from trading_signals"
    if where:
        sql += " where " + " and ".join(where)
    sql += " order by d asc"
    if max_dates:
        sql += " limit %s"
        params.append(max_dates)
    cur.execute(sql, params)
    return [row[0] for row in cur.fetchall()]


def extract_daily_return(event: dict[str, Any], horizon: str) -> float | None:
    outcome = event.get("outcome") or {}
    # DAILY_ENTRY_CANDIDATE/EXIT_SIGNAL stores daily outcome directly.
    daily = outcome.get("daily_signal_outcome") if isinstance(outcome.get("daily_signal_outcome"), dict) else outcome
    if not isinstance(daily, dict):
        return None
    h = daily.get(horizon) or {}
    value = h.get("return_close_pct") if isinstance(h, dict) else None
    return float(value) if value is not None else None


def extract_intraday_return(event: dict[str, Any]) -> float | None:
    outcome = event.get("outcome") or {}
    intraday = outcome.get("intraday") or {}
    value = intraday.get("net_return_pct") if isinstance(intraday, dict) else None
    return float(value) if value is not None else None


def extract_blocked_proxy_return(event: dict[str, Any]) -> float | None:
    outcome = event.get("outcome") or {}
    intraday = outcome.get("intraday") or {}
    value = intraday.get("blocked_proxy_return_to_time_exit_pct") if isinstance(intraday, dict) else None
    return float(value) if value is not None else None


def aggregate_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    event_type_counts = Counter(str(e.get("event_type")) for e in events)
    blocking_counts = Counter()
    blocked_by_reason: dict[str, list[dict[str, Any]]] = defaultdict(list)

    daily_entry_after_1d: list[float] = []
    daily_entry_after_3d: list[float] = []
    blocked_after_1d: list[float] = []
    blocked_after_3d: list[float] = []
    entry_after_1d: list[float] = []
    entry_after_3d: list[float] = []
    entry_intraday_net: list[float] = []
    blocked_intraday_proxy: list[float] = []
    sell_after_1d: list[float] = []
    sell_after_3d: list[float] = []

    by_date: dict[str, Counter[str]] = defaultdict(Counter)
    by_stock: dict[str, Counter[str]] = defaultdict(Counter)

    for e in events:
        event_type = str(e.get("event_type"))
        stock_code = str(e.get("stock_code") or "")
        trading_date = str(e.get("trading_date") or "")
        by_date[trading_date][event_type] += 1
        if stock_code:
            by_stock[stock_code][event_type] += 1
        for reason in e.get("blocking_conditions") or []:
            reason_text = str(reason)
            blocking_counts[reason_text] += 1
            blocked_by_reason[reason_text].append(e)

        r1 = extract_daily_return(e, "after_1d")
        r3 = extract_daily_return(e, "after_3d")
        if event_type == "DAILY_ENTRY_CANDIDATE":
            if r1 is not None:
                daily_entry_after_1d.append(r1)
            if r3 is not None:
                daily_entry_after_3d.append(r3)
        elif event_type == "BLOCKED_ENTRY_SIGNAL":
            blocked_proxy = extract_blocked_proxy_return(e)
            if r1 is not None:
                blocked_after_1d.append(r1)
            if r3 is not None:
                blocked_after_3d.append(r3)
            # Prefer an intraday post-block proxy when available. If not, use
            # next-day daily return as a slower missed-entry proxy.
            if blocked_proxy is not None:
                blocked_intraday_proxy.append(blocked_proxy)
            elif r1 is not None:
                blocked_intraday_proxy.append(r1)
        elif event_type == "INTRADAY_ENTRY_SIGNAL":
            net = extract_intraday_return(e)
            if net is not None:
                entry_intraday_net.append(net)
            if r1 is not None:
                entry_after_1d.append(r1)
            if r3 is not None:
                entry_after_3d.append(r3)
        elif event_type == "EXIT_SIGNAL":
            if r1 is not None:
                sell_after_1d.append(r1)
            if r3 is not None:
                sell_after_3d.append(r3)

    reason_outcomes = {}
    for reason, items in blocked_by_reason.items():
        reason_outcomes[reason] = {
            "events": len(items),
            "after_1d": ret_summary([r for r in (extract_daily_return(e, "after_1d") for e in items) if r is not None]),
            "after_3d": ret_summary([r for r in (extract_daily_return(e, "after_3d") for e in items) if r is not None]),
        }

    return {
        "event_type_counts": dict(event_type_counts),
        "blocking_condition_counts": dict(blocking_counts),
        "daily_entry_candidate_after_1d": ret_summary(daily_entry_after_1d),
        "daily_entry_candidate_after_3d": ret_summary(daily_entry_after_3d),
        "blocked_entry_after_1d": ret_summary(blocked_after_1d),
        "blocked_entry_after_3d": ret_summary(blocked_after_3d),
        "intraday_entry_after_1d": ret_summary(entry_after_1d),
        "intraday_entry_after_3d": ret_summary(entry_after_3d),
        "intraday_entry_net_return": ret_summary(entry_intraday_net),
        "blocked_entry_next_day_proxy_return": ret_summary(blocked_intraday_proxy),
        "sell_signal_after_1d": ret_summary(sell_after_1d),
        "sell_signal_after_3d": ret_summary(sell_after_3d),
        "blocked_by_reason_outcomes": reason_outcomes,
        "by_trading_date": {k: dict(v) for k, v in sorted(by_date.items())},
        "top_stock_event_counts": {
            k: dict(v)
            for k, v in sorted(by_stock.items(), key=lambda kv: sum(kv[1].values()), reverse=True)[:20]
        },
    }


def compare_blocked_vs_entry(summary: dict[str, Any]) -> dict[str, Any]:
    blocked = summary["blocked_entry_next_day_proxy_return"]
    entry = summary["intraday_entry_net_return"]
    result = {
        "blocked_proxy": blocked,
        "intraday_entry_net": entry,
        "interpretation": "insufficient_comparable_samples",
        "avg_diff_blocked_minus_entry_pct": None,
    }
    if blocked.get("avg_pct") is not None and entry.get("avg_pct") is not None:
        diff = round(float(blocked["avg_pct"]) - float(entry["avg_pct"]), 4)
        result["avg_diff_blocked_minus_entry_pct"] = diff
        if diff > 0:
            result["interpretation"] = "blocked_candidates_outperformed_entries_on_available_proxy"
        elif diff < 0:
            result["interpretation"] = "executed_intraday_entries_outperformed_blocked_candidates_on_available_proxy"
        else:
            result["interpretation"] = "blocked_and_entry_proxy_returns_equal"
    return result


def write_markdown(path: Path, data: dict[str, Any]) -> None:
    summary = data["summary"]
    comparison = data["blocked_vs_entry_comparison"]
    lines = [
        "# 누적 signal_events 백테스트 리포트",
        "",
        f"- 생성 시각: `{data['generated_at']}`",
        f"- 대상 signal_date 수: `{data['signal_date_count']}`",
        f"- 대상 signal_dates: `{', '.join(data['signal_dates']) if data['signal_dates'] else 'none'}`",
        f"- 대상 신호 수: `{data['signal_count']}`",
        f"- 생성 이벤트 수: `{data['event_count']}`",
        f"- record_events: `{data['record_events']}`",
        "- 안전 상태: 주문/포지션 미변경, signal_events만 선택적으로 upsert",
        "",
        "## 이벤트 카운트",
        "",
        "| event_type | count |",
        "|---|---:|",
    ]
    for key, value in sorted(summary["event_type_counts"].items()):
        lines.append(f"| {key} | {value} |")

    lines += [
        "",
        "## 차단된 신호 vs 진입 신호 비교",
        "",
        "| group | count | avg_pct | positive_rate_pct | min | max |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, key in [
        ("BLOCKED_ENTRY_SIGNAL next-day proxy", "blocked_entry_next_day_proxy_return"),
        ("INTRADAY_ENTRY_SIGNAL net", "intraday_entry_net_return"),
        ("INTRADAY_ENTRY_SIGNAL after_1d", "intraday_entry_after_1d"),
        ("DAILY_ENTRY_CANDIDATE after_1d", "daily_entry_candidate_after_1d"),
    ]:
        s = summary[key]
        lines.append(f"| {label} | {s['count']} | {s['avg_pct']} | {s['positive_rate_pct']} | {s['min_pct']} | {s['max_pct']} |")
    lines += [
        "",
        f"- 비교 판정: `{comparison['interpretation']}`",
        f"- blocked 평균 - entry 평균: `{comparison['avg_diff_blocked_minus_entry_pct']}` pct",
        "",
        "## Daily/SELL 후속 수익률",
        "",
        "| signal_group | horizon | count | avg_pct | positive_rate_pct | min | max |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for label, key in [
        ("DAILY_ENTRY_CANDIDATE", "daily_entry_candidate_after_1d"),
        ("DAILY_ENTRY_CANDIDATE", "daily_entry_candidate_after_3d"),
        ("BLOCKED_ENTRY_SIGNAL", "blocked_entry_after_1d"),
        ("BLOCKED_ENTRY_SIGNAL", "blocked_entry_after_3d"),
        ("EXIT_SIGNAL", "sell_signal_after_1d"),
        ("EXIT_SIGNAL", "sell_signal_after_3d"),
    ]:
        horizon = "after_3d" if key.endswith("3d") else "after_1d"
        s = summary[key]
        lines.append(f"| {label} | {horizon} | {s['count']} | {s['avg_pct']} | {s['positive_rate_pct']} | {s['min_pct']} | {s['max_pct']} |")

    lines += ["", "## 차단 조건별 이후 수익률", "", "| reason | events | after_1d count | after_1d avg | after_3d count | after_3d avg |", "|---|---:|---:|---:|---:|---:|"]
    for reason, s in sorted(summary["blocked_by_reason_outcomes"].items(), key=lambda kv: (-kv[1]["events"], kv[0])):
        lines.append(
            f"| {reason} | {s['events']} | {s['after_1d']['count']} | {s['after_1d']['avg_pct']} | {s['after_3d']['count']} | {s['after_3d']['avg_pct']} |"
        )

    lines += ["", "## 날짜별 이벤트 수", "", "| trading_date | counts |", "|---|---|"]
    for d, counts in summary["by_trading_date"].items():
        lines.append(f"| {d} | `{json.dumps(counts, ensure_ascii=False)}` |")

    lines += [
        "",
        "## 운영 판단",
        "",
        "- 표본이 충분하지 않거나 after_1d/3d 일봉 데이터가 아직 없으면 비교 판정은 보류입니다.",
        "- `blocked_entry_next_day_proxy_return`은 차단 후보가 이후 상승했는지 보는 대체 지표입니다.",
        "- `intraday_entry_net_return`이 음수이면 paper/real 주문 전환 금지를 유지합니다.",
        "- 전략 threshold/weight/order behavior 변경은 이 누적 리포트 검토 후 별도로 결정합니다.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", help="YYYY-MM-DD inclusive")
    parser.add_argument("--end-date", help="YYYY-MM-DD inclusive")
    parser.add_argument("--max-dates", type=int)
    parser.add_argument("--limit-per-date", type=int, default=500)
    parser.add_argument("--record-events", action="store_true")
    parser.add_argument("--keep-existing-events", action="store_true")
    parser.add_argument("--fee-bps", type=float, default=23.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--stop-loss-pct", type=float, default=-1.0)
    parser.add_argument("--take-profit-pct", type=float, default=1.5)
    parser.add_argument("--time-exit", default="15:20")
    parser.add_argument("--json-out", default="reports/signal_event_outcomes_batch_latest.json")
    parser.add_argument("--md-out", default="reports/signal_event_outcomes_batch_latest.md")
    args = parser.parse_args()

    env = read_env(PROJECT_ROOT / ".env")
    if not env.get("DATABASE_URL"):
        out = {"ok": False, "status": "blocked", "blocking_conditions": ["missing_database_url"]}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    all_events: list[dict[str, Any]] = []
    per_date: list[dict[str, Any]] = []
    deleted_total = 0
    signal_count = 0

    with psycopg.connect(env["DATABASE_URL"], connect_timeout=20, prepare_threshold=None) as conn:
        single.ensure_signal_events_table(conn)
        with conn.cursor() as cur:
            dates = fetch_signal_dates(cur, parse_day(args.start_date), parse_day(args.end_date), args.max_dates)
            if not dates:
                out = {"ok": False, "status": "blocked", "blocking_conditions": ["no_signal_dates_found"]}
                print(json.dumps(out, ensure_ascii=False, indent=2))
                return 2
            for signal_day in dates:
                signals = single.fetch_signals(cur, signal_day, args.limit_per_date)
                signal_count += len(signals)
                day_events: list[dict[str, Any]] = []
                for sig in signals:
                    day_events.extend(
                        single.build_events_for_signal(
                            cur,
                            sig,
                            fee_bps_one_way=args.fee_bps,
                            slippage_bps_one_way=args.slippage_bps,
                            stop_loss_pct=args.stop_loss_pct,
                            take_profit_pct=args.take_profit_pct,
                            time_exit=args.time_exit,
                        )
                    )
                if args.record_events:
                    if not args.keep_existing_events:
                        deleted_total += single.delete_existing_events_for_signals(cur, [int(s["id"]) for s in signals])
                    single.upsert_events(cur, day_events)
                    conn.commit()
                all_events.extend(day_events)
                per_date.append(
                    {
                        "signal_date": str(signal_day),
                        "signal_count": len(signals),
                        "event_count": len(day_events),
                        "summary": aggregate_events(day_events),
                    }
                )

    summary = aggregate_events(all_events)
    comparison = compare_blocked_vs_entry(summary)
    data = {
        "ok": True,
        "stage": "backtest_signal_event_outcomes_batch",
        "status": "completed",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "signal_dates": [str(d) for d in dates],
        "signal_date_count": len(dates),
        "signal_count": signal_count,
        "event_count": len(all_events),
        "record_events": args.record_events,
        "deleted_existing_events": deleted_total,
        "summary": summary,
        "blocked_vs_entry_comparison": comparison,
        "per_date": per_date,
        "events_sample": all_events[:100],
        "blocking_conditions": [],
        "alerts": [] if len(dates) > 1 else ["only_one_signal_date_available_in_trading_signals"],
        "next_actions": [
            "과거 signal_date가 1개뿐이면 daily signal backfill 또는 과거 신호 재생성을 먼저 수행하세요.",
            "blocked_entry_next_day_proxy_return이 intraday_entry_net_return보다 높으면 opening layer 과도 차단을 의심하세요.",
            "INTRADAY_ENTRY_SIGNAL 평균 순수익률이 음수면 paper/real 전환 금지를 유지하세요.",
        ],
    }
    json_path = PROJECT_ROOT / args.json_out
    md_path = PROJECT_ROOT / args.md_out
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_markdown(md_path, data)

    printable = {k: v for k, v in data.items() if k not in {"events_sample", "per_date"}}
    printable["json_out"] = str(json_path)
    printable["md_out"] = str(md_path)
    print(json.dumps(printable, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
