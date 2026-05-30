"""Backtest Fujimoto 1-2-6 filter on real ka10080 1-minute bars.

Safety:
- Read-only: only reads trading_signals/intraday_prices and writes report files.
- Uses source=kiwoom_ka10080_minute and time_frame=1min only.
- Does not call Kiwoom order APIs and never writes orders/positions.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.fujimoto_126_filter import PriceBar, STRATEGY_ID, simulate_fujimoto_126_trade  # noqa: E402
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


def parse_day(text: str | None) -> date | None:
    return datetime.fromisoformat(text[:10]).date() if text else None


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
        select id, stock_code, signal_date, price, price_at_signal, score, signal_strength, strategy, score_details
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
        where stock_code=%s and source=%s and time_frame=%s
          and (timestamp at time zone 'Asia/Seoul')::date > %s
        """,
        (stock_code, SOURCE, TIME_FRAME, signal_day),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] else None


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
    out: list[PriceBar] = []
    for ts, o, h, l, c, v in cur.fetchall():
        kst = ts_to_kst(ts)
        out.append(PriceBar(kst, kst.strftime("%H:%M"), num(o), num(h), num(l), num(c), int(v or 0)))
    return out


def fetch_stock_days(cur: Any, start: date | None, end: date | None, stock_code: str | None, limit: int) -> list[dict[str, Any]]:
    params: list[Any] = [SOURCE, TIME_FRAME]
    where = ["source=%s", "time_frame=%s"]
    if stock_code:
        where.append("stock_code=%s")
        params.append(stock_code)
    if start:
        where.append("(timestamp at time zone 'Asia/Seoul')::date >= %s")
        params.append(start)
    if end:
        where.append("(timestamp at time zone 'Asia/Seoul')::date <= %s")
        params.append(end)
    params.append(limit)
    cur.execute(
        f"""
        select stock_code, (timestamp at time zone 'Asia/Seoul')::date as trading_day, count(*) as rows
        from intraday_prices
        where {' and '.join(where)}
        group by stock_code, (timestamp at time zone 'Asia/Seoul')::date
        order by trading_day desc, stock_code asc
        limit %s
        """,
        params,
    )
    return [{"stock_code": row[0], "trading_day": row[1], "rows": int(row[2])} for row in cur.fetchall()]


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    entries = [row for row in results if row.get("ok")]
    blocked = [row for row in results if not row.get("ok")]
    returns = [float(row["net_return_pct"]) for row in entries if row.get("net_return_pct") is not None]
    blocks = Counter(reason for row in blocked + entries for reason in row.get("blocking_conditions", []) if reason)
    exits = Counter(str(row.get("exit_reason")) for row in entries if row.get("exit_reason"))
    stages = Counter(str(row.get("entry_stage") or row.get("position_stage") or "NONE") for row in results)
    return {
        "signals_or_stock_days_seen": len(results),
        "entries": len(entries),
        "blocked": len(blocked),
        "entry_rate_pct": round(len(entries) / len(results) * 100.0, 2) if results else None,
        "returns": ret_summary(returns),
        "exit_reason_counts": dict(exits),
        "stage_counts": dict(stages),
        "blocking_condition_counts": dict(blocks),
    }


def write_markdown(path: Path, data: dict[str, Any]) -> None:
    summary = data["summary"]
    ret = summary["returns"]
    lines = [
        "# 후지모토 1-2-6 전략 백테스트 리포트",
        "",
        f"- 생성 시각: `{data['generated_at']}`",
        f"- 전략: `{STRATEGY_ID}`",
        f"- 실행 모드: `{data['mode']}`",
        f"- 데이터: `intraday_prices`, source=`{SOURCE}`, time_frame=`{TIME_FRAME}`",
        "- 안전 상태: read-only 백테스트, 주문/포지션 미변경, paper/real 주문 금지",
        "",
        "## 요약",
        "",
        "| 평가대상 | 진입 | 차단 | 진입률 | 평균 net% | 승률 | min | max |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| {summary['signals_or_stock_days_seen']} | {summary['entries']} | {summary['blocked']} | {summary['entry_rate_pct']} | {ret['avg_pct']} | {ret['positive_rate_pct']} | {ret['min_pct']} | {ret['max_pct']} |",
        "",
        "## 종료/차단 조건",
        "",
        f"- exit_reason_counts: `{json.dumps(summary['exit_reason_counts'], ensure_ascii=False)}`",
        f"- stage_counts: `{json.dumps(summary['stage_counts'], ensure_ascii=False)}`",
        f"- blocking_condition_counts: `{json.dumps(summary['blocking_condition_counts'], ensure_ascii=False)}`",
        "",
        "## 해석",
        "",
        *[f"- {item}" for item in data.get("interpretation", [])],
        "",
        "## 샘플 결과 상위 20개",
        "",
        "| date | code | ok | entry | exit | net% | blocks |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in data.get("results", [])[:20]:
        lines.append(
            f"| {row.get('entry_trading_date') or row.get('trading_day')} | {row.get('stock_code')} | {row.get('ok')} | "
            f"{row.get('entry_time')} | {row.get('exit_time')} | {row.get('net_return_pct')} | "
            f"`{json.dumps(row.get('blocking_conditions', []), ensure_ascii=False)}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_interpretation(data: dict[str, Any]) -> list[str]:
    summary = data["summary"]
    out = []
    if summary["signals_or_stock_days_seen"] == 0:
        out.append("평가 가능한 실제 ka10080 1분봉 대상이 없습니다. 수집/날짜/종목 필터를 먼저 확인해야 합니다.")
    if summary["entries"] == 0:
        out.append("후지모토 1-2-6 full-stage 진입이 0건입니다. RSI/MACD/일목 동시조건이 과도하거나 데이터 표본이 부족할 수 있습니다.")
    elif summary["entries"] < 10:
        out.append("진입 표본이 10건 미만입니다. 성과 판단보다 조건/차트 검증이 우선입니다.")
    if summary["returns"]["avg_pct"] is not None and summary["returns"]["avg_pct"] <= 0:
        out.append("현재 평균 순수익률이 0 이하입니다. paper/real 전환 금지 상태를 유지해야 합니다.")
    out.append("이 백테스트 결과만으로 threshold/weight/order behavior를 변경하지 마세요. 날짜별 1분봉 차트 검증이 다음 단계입니다.")
    out.append("paper_order_allowed=false, real_order_allowed=false가 정상입니다.")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["signals", "stock-days"], default="signals", help="signals: trading_signals BUY 다음 거래일 replay, stock-days: 분봉 보유 stock×date 직접 평가")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--stock-code")
    parser.add_argument("--limit-per-date", type=int, default=30)
    parser.add_argument("--stock-day-limit", type=int, default=100)
    parser.add_argument("--min-score", type=float, default=60.0)
    parser.add_argument("--stop-loss-pct", type=float, default=-2.0)
    parser.add_argument("--take-profit-pct", type=float, default=3.0)
    parser.add_argument("--time-exit", default="15:20")
    parser.add_argument("--fee-bps", type=float, default=23.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--json-out", default="reports/fujimoto_126_backtest_latest.json")
    parser.add_argument("--md-out", default="reports/fujimoto_126_backtest_latest.md")
    args = parser.parse_args()

    env = read_env(PROJECT_ROOT / ".env")
    if not env.get("DATABASE_URL"):
        print(json.dumps({"ok": False, "blocking_conditions": ["missing_database_url"]}, ensure_ascii=False, indent=2))
        return 2

    import psycopg

    results: list[dict[str, Any]] = []
    missing_next_day = 0
    signal_dates: list[date] = []
    with psycopg.connect(env["DATABASE_URL"], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            if args.mode == "signals":
                signal_dates = fetch_signal_dates(cur, parse_day(args.start_date), parse_day(args.end_date))
                for signal_day in signal_dates:
                    signals = fetch_buy_signals(cur, signal_day, args.limit_per_date)
                    for sig in signals:
                        code = str(sig["stock_code"])
                        if args.stock_code and code != args.stock_code:
                            continue
                        next_day = next_minute_trading_day(cur, code, signal_day)
                        if next_day is None:
                            missing_next_day += 1
                            continue
                        bars = fetch_bars(cur, code, next_day)
                        if not bars:
                            missing_next_day += 1
                            continue
                        outcome = simulate_fujimoto_126_trade(
                            bars,
                            min_score=args.min_score,
                            stop_loss_pct=args.stop_loss_pct,
                            take_profit_pct=args.take_profit_pct,
                            time_exit=args.time_exit,
                            fee_bps=args.fee_bps,
                            slippage_bps=args.slippage_bps,
                        )
                        results.append({
                            "signal_date": str(signal_day),
                            "entry_trading_date": str(next_day),
                            "source_signal_id": sig["id"],
                            "stock_code": code,
                            "signal_score": num(sig.get("score") or sig.get("signal_strength")),
                            **outcome,
                        })
            else:
                stock_days = fetch_stock_days(cur, parse_day(args.start_date), parse_day(args.end_date), args.stock_code, args.stock_day_limit)
                for item in stock_days:
                    code = str(item["stock_code"])
                    trading_day = item["trading_day"]
                    bars = fetch_bars(cur, code, trading_day)
                    outcome = simulate_fujimoto_126_trade(
                        bars,
                        min_score=args.min_score,
                        stop_loss_pct=args.stop_loss_pct,
                        take_profit_pct=args.take_profit_pct,
                        time_exit=args.time_exit,
                        fee_bps=args.fee_bps,
                        slippage_bps=args.slippage_bps,
                    )
                    results.append({"trading_day": str(trading_day), "stock_code": code, "minute_rows": len(bars), **outcome})

    summary = aggregate(results)
    data = {
        "ok": True,
        "stage": "fujimoto_126_backtest",
        "mode": args.mode,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE,
        "time_frame": TIME_FRAME,
        "signal_dates": [str(d) for d in signal_dates],
        "missing_next_day_minute_count": missing_next_day,
        "parameters": vars(args),
        "summary": summary,
        "results": results,
        "blocking_conditions": [],
        "alerts": [],
    }
    data["interpretation"] = build_interpretation(data)
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
