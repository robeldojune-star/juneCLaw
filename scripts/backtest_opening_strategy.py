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


def _simulate_variant(rows: list[dict[str, Any]], minutes: int) -> dict[str, Any]:
    # Simplified simulation on available bar series.
    # Entry: break above first-bar high; Exit: close at last bar.
    trades = 0
    wins = 0
    rets: list[float] = []
    by_day: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        ts = str(r.get("timestamp") or "")
        day = ts[:10]
        by_day.setdefault(day, []).append(r)
    for day, day_rows in by_day.items():
        if len(day_rows) < max(3, minutes // 5):
            continue
        day_rows.sort(key=lambda x: str(x.get("timestamp") or ""))
        opening = day_rows[0]
        opening_high = num(opening.get("high"))
        if opening_high <= 0:
            continue
        entry = None
        for bar in day_rows[1:]:
            if num(bar.get("high")) > opening_high:
                entry = num(bar.get("close"))
                break
        if not entry or entry <= 0:
            continue
        exit_price = num(day_rows[-1].get("close"))
        if exit_price <= 0:
            continue
        ret = (exit_price - entry) / entry * 100.0
        trades += 1
        if ret > 0:
            wins += 1
        rets.append(ret)
    avg_ret = sum(rets) / len(rets) if rets else None
    win_rate = (wins / trades * 100.0) if trades else None
    max_dd = min(rets) if rets else None
    return {
        "trades": trades,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "avg_return_pct": round(avg_ret, 4) if avg_ret is not None else None,
        "max_drawdown_pct": round(max_dd, 4) if max_dd is not None else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-codes", nargs="+", default=["005930"])
    parser.add_argument("--days", type=int, default=130)
    parser.add_argument("--time-frame", default="1min")
    parser.add_argument("--min-rows", type=int, default=300)
    parser.add_argument("--min-trades", type=int, default=5)
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
            rows = sb.get(
                "intraday_prices",
                {
                    "select": "stock_code,timestamp,time_frame,open,high,low,close,volume,trading_value",
                    "stock_code": f"eq.{code}",
                    "time_frame": f"eq.{args.time_frame}",
                    "timestamp": f"gte.{since}",
                    "order": "timestamp.asc",
                    "limit": "5000",
                },
            )
            all_rows.extend(rows)
        except SupabaseRestError as exc:
            alerts.append(f"{code}_intraday_query_failed:{exc}")

    if not all_rows:
        blocks.append("need_90_trading_days_intraday_prices")
    elif len(all_rows) < args.min_rows:
        blocks.append("insufficient_intraday_rows_for_backtest")

    grouped = _group_by_stock(all_rows)
    v10 = {code: _simulate_variant(rows, 10) for code, rows in grouped.items()}
    v30 = {code: _simulate_variant(rows, 30) for code, rows in grouped.items()}

    total_trades = sum(v.get("trades", 0) for v in v10.values()) + sum(v.get("trades", 0) for v in v30.values())
    if all_rows and total_trades < args.min_trades:
        blocks.append("insufficient_backtest_trade_count")

    def agg(variant: dict[str, dict[str, Any]]) -> dict[str, Any]:
        trades = sum(v.get("trades", 0) for v in variant.values())
        wrs = [v.get("win_rate") for v in variant.values() if v.get("win_rate") is not None]
        ars = [v.get("avg_return_pct") for v in variant.values() if v.get("avg_return_pct") is not None]
        mdds = [v.get("max_drawdown_pct") for v in variant.values() if v.get("max_drawdown_pct") is not None]
        return {
            "trades": trades,
            "win_rate": round(sum(wrs) / len(wrs), 4) if wrs else None,
            "avg_return_pct": round(sum(ars) / len(ars), 4) if ars else None,
            "max_drawdown_pct": round(min(mdds), 4) if mdds else None,
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
            "rows_used": len(all_rows),
            "min_rows_required": args.min_rows,
            "total_variant_trades": total_trades,
            "min_trades_required": args.min_trades,
        },
        "blocking_conditions": blocks,
        "alerts": alerts,
        "next_actions": [
            "rows_used가 작으면 collect_intraday_90d 스케줄을 장중 반복으로 늘리세요",
            "ka10005_timeframe_validation 통과 전 자동 주문을 활성화하지 마세요",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
