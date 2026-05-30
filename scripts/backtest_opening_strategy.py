"""Backtest opening strategy variants using real intraday_prices from Supabase.

No fake data. If data is insufficient, returns blocked status.
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

from core.supabase_rest import SupabaseRestClient, SupabaseRestError, num  # noqa: E402


def _group_by_stock(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        code = str(r.get("stock_code") or "")
        if not code:
            continue
        out.setdefault(code, []).append(r)
    for code in out:
        out[code].sort(key=lambda x: str(x.get("timestamp") or ""))
    return out


def _parse_ts_kst(row: dict[str, Any]) -> datetime | None:
    value = row.get("timestamp")
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
    return dt.astimezone(timezone(timedelta(hours=9)))


def _minute_range(start_hhmm: str, end_hhmm: str) -> set[str]:
    base = "2026-01-01"
    cur = datetime.fromisoformat(f"{base}T{start_hhmm}:00+09:00")
    end = datetime.fromisoformat(f"{base}T{end_hhmm}:00+09:00")
    out: set[str] = set()
    while cur <= end:
        out.add(cur.strftime("%H:%M"))
        cur = cur.replace(minute=cur.minute + 1) if cur.minute < 59 else cur.replace(hour=cur.hour + 1, minute=0)
    return out


def _filter_eligible_opening_days(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected = _minute_range("09:00", "09:30")
    by_code_day: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        code = str(row.get("stock_code") or "")
        ts = _parse_ts_kst(row)
        if not code or ts is None:
            continue
        by_code_day.setdefault((code, ts.strftime("%Y-%m-%d")), []).append(row)

    eligible_rows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for (code, day), day_rows in sorted(by_code_day.items()):
        counts: dict[str, int] = {}
        for row in day_rows:
            ts = _parse_ts_kst(row)
            if ts is None:
                continue
            hhmm = ts.strftime("%H:%M")
            counts[hhmm] = counts.get(hhmm, 0) + 1
        missing = sorted(expected - set(counts))
        duplicate_opening = sum(max(0, count - 1) for hhmm, count in counts.items() if hhmm in expected)
        if missing or duplicate_opening:
            excluded.append({
                "stock_code": code,
                "date": day,
                "rows": len(day_rows),
                "missing_opening_minutes": len(missing),
                "missing_opening_sample": missing[:10],
                "duplicate_opening_minutes": duplicate_opening,
            })
        else:
            eligible_rows.extend(day_rows)
    return eligible_rows, {
        "eligible_filter_enabled": True,
        "opening_required_minutes": "09:00~09:30",
        "eligible_stock_days": len({(str(r.get("stock_code") or ""), (_parse_ts_kst(r) or datetime.min.replace(tzinfo=timezone.utc)).strftime("%Y-%m-%d")) for r in eligible_rows}),
        "excluded_stock_days": len(excluded),
        "excluded_examples": excluded[:30],
    }


def _simulate_variant(
    rows: list[dict[str, Any]],
    minutes: int,
    *,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
    stop_loss_pct: float = -1.0,
    take_profit_pct: float = 1.5,
    time_exit: str = "15:20",
) -> dict[str, Any]:
    """Simulate true OR10/OR30 breakout.

    Signal definition:
    - Build opening range from 09:00 through 09:00+minutes.
    - Do not enter during the range-building period.
    - Signal/entry occurs only after the range is complete and price breaks the range high.
    - Exit uses the last available bar close for now.
    """
    trades = 0
    wins = 0
    rets: list[float] = []
    entry_times: list[str] = []
    exit_reason_counts: dict[str, int] = {}
    by_day: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        ts = _parse_ts_kst(r)
        if ts is None:
            continue
        day = ts.strftime("%Y-%m-%d")
        by_day.setdefault(day, []).append(r)
    for _day, day_rows in by_day.items():
        day_rows.sort(key=lambda x: str(x.get("timestamp") or ""))
        range_end = "09:10" if minutes == 10 else "09:30"
        range_rows: list[dict[str, Any]] = []
        entry_candidates: list[dict[str, Any]] = []
        for bar in day_rows:
            ts = _parse_ts_kst(bar)
            if ts is None:
                continue
            hhmm = ts.strftime("%H:%M")
            if "09:00" <= hhmm <= range_end:
                range_rows.append(bar)
            elif hhmm > range_end:
                entry_candidates.append(bar)
        expected_count = minutes + 1
        if len({(_parse_ts_kst(b) or datetime.min.replace(tzinfo=timezone.utc)).strftime("%H:%M") for b in range_rows}) < expected_count:
            continue
        opening_high = max(num(bar.get("high")) for bar in range_rows)
        if opening_high <= 0:
            continue
        entry = None
        entry_time = None
        entry_idx = None
        for idx, bar in enumerate(entry_candidates):
            if num(bar.get("high")) > opening_high:
                entry = num(bar.get("close"))
                ts = _parse_ts_kst(bar)
                entry_time = ts.strftime("%H:%M") if ts else None
                entry_idx = idx
                break
        if not entry or entry <= 0:
            continue
        exit_price = None
        exit_reason = "time_exit_or_last_close"
        post_entry = entry_candidates[entry_idx + 1:] if entry_idx is not None else []
        for bar in post_entry:
            ts = _parse_ts_kst(bar)
            if ts is None:
                continue
            hhmm = ts.strftime("%H:%M")
            low_ret = (num(bar.get("low")) - entry) / entry * 100.0
            high_ret = (num(bar.get("high")) - entry) / entry * 100.0
            if low_ret <= stop_loss_pct:
                exit_price = entry * (1 + stop_loss_pct / 100.0)
                exit_reason = "stop_loss_sell_signal"
                break
            if high_ret >= take_profit_pct:
                exit_price = entry * (1 + take_profit_pct / 100.0)
                exit_reason = "take_profit_sell_signal"
                break
            if hhmm >= time_exit:
                exit_price = num(bar.get("close"))
                exit_reason = "time_exit_sell_signal"
                break
        if exit_price is None:
            exit_price = num(day_rows[-1].get("close"))
        if exit_price <= 0:
            continue
        gross_ret = (exit_price - entry) / entry * 100.0
        cost_pct = (fee_bps + slippage_bps) / 100.0 * 2
        ret = gross_ret - cost_pct
        trades += 1
        if ret > 0:
            wins += 1
        rets.append(ret)
        if entry_time:
            entry_times.append(entry_time)
        exit_reason_counts[exit_reason] = exit_reason_counts.get(exit_reason, 0) + 1
    avg_ret = sum(rets) / len(rets) if rets else None
    win_rate = (wins / trades * 100.0) if trades else None
    max_dd = min(rets) if rets else None
    return {
        "trades": trades,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "avg_return_pct": round(avg_ret, 4) if avg_ret is not None else None,
        "max_drawdown_pct": round(max_dd, 4) if max_dd is not None else None,
        "entry_time_min": min(entry_times) if entry_times else None,
        "entry_time_max": max(entry_times) if entry_times else None,
        "exit_reason_counts": exit_reason_counts,
    }


def _fetch_intraday_rows(
    sb: SupabaseRestClient,
    *,
    stock_code: str,
    time_frame: str,
    source: str,
    since: str,
    page_size: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    page_size = max(1, page_size)
    while True:
        page = sb.get(
            "intraday_prices",
            {
                "select": "stock_code,timestamp,time_frame,source,open,high,low,close,volume,trading_value",
                "stock_code": f"eq.{stock_code}",
                "time_frame": f"eq.{time_frame}",
                "source": f"eq.{source}",
                "timestamp": f"gte.{since}",
                "order": "timestamp.asc",
                "limit": str(page_size),
                "offset": str(offset),
            },
        )
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
        if offset > 200000:
            break
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-codes", nargs="+", default=["005930"])
    parser.add_argument("--days", type=int, default=130)
    parser.add_argument("--time-frame", default="1min")
    parser.add_argument("--source", default="kiwoom_ka10080_minute")
    parser.add_argument("--min-rows", type=int, default=300)
    parser.add_argument("--min-trades", type=int, default=5)
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--eligible-opening-only", action="store_true", help="Use only stock-days with complete 09:00~09:30 bars.")
    parser.add_argument("--fee-bps", type=float, default=0.0, help="One-way fee/tax estimate in basis points.")
    parser.add_argument("--slippage-bps", type=float, default=0.0, help="One-way slippage estimate in basis points.")
    parser.add_argument("--stop-loss-pct", type=float, default=-1.0)
    parser.add_argument("--take-profit-pct", type=float, default=1.5)
    parser.add_argument("--time-exit", default="15:20")
    args = parser.parse_args()

    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat(timespec="seconds")
    blocks: list[str] = []
    alerts: list[str] = []

    try:
        sb = SupabaseRestClient()
    except SupabaseRestError as exc:
        out = {
            "ok": False,
            "workflow": "backtest_opening_range",
            "strategy_id": "opening_multi_factor_v1",
            "status": "blocked",
            "blocking_conditions": [str(exc)],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    all_rows: list[dict[str, Any]] = []
    for code in args.stock_codes:
        try:
            rows = _fetch_intraday_rows(
                sb,
                stock_code=code,
                time_frame=args.time_frame,
                source=args.source,
                since=since,
                page_size=args.page_size,
            )
            all_rows.extend(rows)
        except SupabaseRestError as exc:
            alerts.append(f"{code}_intraday_query_failed:{exc}")

    raw_rows_before_filter = len(all_rows)
    eligibility: dict[str, Any] = {"eligible_filter_enabled": args.eligible_opening_only}
    if args.eligible_opening_only and all_rows:
        all_rows, eligibility = _filter_eligible_opening_days(all_rows)

    if not all_rows:
        blocks.append("need_90_trading_days_intraday_prices")
    elif len(all_rows) < args.min_rows:
        blocks.append("insufficient_intraday_rows_for_backtest")

    grouped = _group_by_stock(all_rows)
    v10 = {code: _simulate_variant(rows, 10, fee_bps=args.fee_bps, slippage_bps=args.slippage_bps, stop_loss_pct=args.stop_loss_pct, take_profit_pct=args.take_profit_pct, time_exit=args.time_exit) for code, rows in grouped.items()}
    v30 = {code: _simulate_variant(rows, 30, fee_bps=args.fee_bps, slippage_bps=args.slippage_bps, stop_loss_pct=args.stop_loss_pct, take_profit_pct=args.take_profit_pct, time_exit=args.time_exit) for code, rows in grouped.items()}

    total_trades = sum(v.get("trades", 0) for v in v10.values()) + sum(v.get("trades", 0) for v in v30.values())
    if all_rows and total_trades < args.min_trades:
        blocks.append("insufficient_backtest_trade_count")

    def agg(variant: dict[str, dict[str, Any]]) -> dict[str, Any]:
        trades = sum(v.get("trades", 0) for v in variant.values())
        wrs = [v.get("win_rate") for v in variant.values() if v.get("win_rate") is not None]
        ars = [v.get("avg_return_pct") for v in variant.values() if v.get("avg_return_pct") is not None]
        mdds = [v.get("max_drawdown_pct") for v in variant.values() if v.get("max_drawdown_pct") is not None]
        exit_reasons: dict[str, int] = {}
        for v in variant.values():
            for reason, count in (v.get("exit_reason_counts") or {}).items():
                exit_reasons[str(reason)] = exit_reasons.get(str(reason), 0) + int(count)
        return {
            "trades": trades,
            "win_rate": round(sum(wrs) / len(wrs), 4) if wrs else None,
            "avg_return_pct": round(sum(ars) / len(ars), 4) if ars else None,
            "max_drawdown_pct": round(min(mdds), 4) if mdds else None,
            "exit_reason_counts": exit_reasons,
        }

    out = {
        "ok": not blocks,
        "workflow": "backtest_opening_range",
        "strategy_id": "opening_multi_factor_v1",
        "status": "completed" if not blocks else "blocked",
        "variants": {
            "opening_10m": agg(v10),
            "opening_30m": agg(v30),
        },
        "per_stock": {
            "opening_10m": v10,
            "opening_30m": v30,
        },
        "summary": {
            "stock_codes": args.stock_codes,
            "days": args.days,
            "time_frame": args.time_frame,
            "source": args.source,
            "rows_used": len(all_rows),
            "raw_rows_before_eligibility_filter": raw_rows_before_filter,
            "min_rows_required": args.min_rows,
            "total_variant_trades": total_trades,
            "min_trades_required": args.min_trades,
            "fee_bps_one_way": args.fee_bps,
            "slippage_bps_one_way": args.slippage_bps,
            "stop_loss_pct": args.stop_loss_pct,
            "take_profit_pct": args.take_profit_pct,
            "time_exit": args.time_exit,
            "eligibility": eligibility,
        },
        "blocking_conditions": blocks,
        "alerts": alerts,
        "next_actions": [
            "rows_used가 작으면 collect_intraday_90d를 ka10080 기반으로 더 긴 기간/종목에 대해 실행하세요",
            "source=kiwoom_ka10080_minute/time_frame=1min 품질 검증 전 자동 주문을 활성화하지 마세요",
            "paper/real 주문은 백테스트 rows/trades/리스크 기준 통과 전까지 계속 금지하세요",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
