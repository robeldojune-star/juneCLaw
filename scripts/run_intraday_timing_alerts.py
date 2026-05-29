"""Evaluate intraday timing alerts from today's watchlist and snapshot_1m rows.

Safe-by-design:
- Uses only intraday_prices rows where source=kiwoom_ka10006_snapshot and time_frame=snapshot_1m.
- Builds/reads today_watchlist via scripts/build_today_watchlist.py.
- Emits alert-only JSON events. It never sends orders and keeps paper/real order flags false.
"""
from __future__ import annotations

import argparse
from datetime import datetime, time
import json
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import SupabaseRestClient, SupabaseRestError, num  # noqa: E402

WORKFLOW = "daily_trading_workflow_v1"
STAGE = "intraday_timing_alert"
KST = ZoneInfo("Asia/Seoul")
UTC = ZoneInfo("UTC")
SNAPSHOT_SOURCE = "kiwoom_ka10006_snapshot"
SNAPSHOT_TIME_FRAME = "snapshot_1m"
ORDER_BLOCKERS = [
    "snapshot_1m_accumulation_and_backtest_required",
    "pattern_model_not_ready_for_auto_order",
    "paper_order_workflow_not_validated",
    "real_order_disabled_until_user_approval",
]


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def _trading_day_bounds(trading_date: str) -> tuple[str, str]:
    y, m, d = map(int, trading_date.split("-"))
    start = datetime(y, m, d, 9, 0, tzinfo=KST)
    end = datetime(y, m, d, 15, 36, tzinfo=KST)
    return start.isoformat(), end.isoformat()


def _run_json(args: list[str], timeout: int = 180) -> tuple[dict[str, Any] | None, str | None, int]:
    proc = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    stdout = (proc.stdout or "").strip()
    try:
        data = json.loads(stdout) if stdout else None
    except json.JSONDecodeError:
        return None, (proc.stderr or stdout)[-1500:], proc.returncode
    return data if isinstance(data, dict) else None, proc.stderr[-1500:] if proc.stderr else None, proc.returncode


def load_today_watchlist(limit: int) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[str], list[str]]:
    data, err, _rc = _run_json([sys.executable, "scripts/build_today_watchlist.py"], timeout=180)
    blocks: list[str] = []
    alerts: list[str] = []
    if data is None:
        blocks.append("today_watchlist_invalid_json")
        if err:
            alerts.append(err)
        return [], None, blocks, alerts
    blocks.extend(str(x) for x in data.get("blocking_conditions", []) if x)
    alerts.extend(str(x) for x in data.get("alerts", []) if x)
    watchlist = data.get("watchlist", []) if isinstance(data.get("watchlist"), list) else []
    watchlist = [w for w in watchlist if isinstance(w, dict) and str(w.get("stock_code") or "")]
    return watchlist[:limit], data, blocks, alerts


def load_snapshot_rows(stock_code: str, trading_date: str, limit: int) -> tuple[list[dict[str, Any]], str | None]:
    start, end = _trading_day_bounds(trading_date)
    try:
        sb = SupabaseRestClient()
        rows = sb.get(
            "intraday_prices",
            {
                "select": "stock_code,timestamp,open,high,low,close,volume,trading_value,source,time_frame",
                "stock_code": f"eq.{stock_code}",
                "time_frame": f"eq.{SNAPSHOT_TIME_FRAME}",
                "source": f"eq.{SNAPSHOT_SOURCE}",
                "timestamp": f"gte.{start}",
                "order": "timestamp.asc",
                "limit": str(limit),
            },
            timeout=20,
        )
    except SupabaseRestError as exc:
        return [], str(exc)

    # PostgREST cannot express two filters with the same key through a normal dict.
    # Keep the lower bound in the REST query and enforce the upper bound locally.
    end_dt = _parse_ts(end)
    filtered: list[dict[str, Any]] = []
    for row in rows:
        ts = _parse_ts(row.get("timestamp"))
        if ts is None:
            continue
        if end_dt and ts >= end_dt:
            continue
        row = dict(row)
        row["_timestamp_kst"] = ts
        filtered.append(row)
    return filtered, None


def _clean_bar(row: dict[str, Any]) -> dict[str, Any] | None:
    open_p = num(row.get("open"))
    high_p = num(row.get("high"))
    low_p = num(row.get("low"))
    close_p = num(row.get("close"))
    volume = num(row.get("volume"))
    if open_p <= 0 or high_p <= 0 or low_p <= 0 or close_p <= 0:
        return None
    if high_p < max(open_p, close_p) or low_p > min(open_p, close_p):
        return None
    return {
        "timestamp": row.get("_timestamp_kst") or _parse_ts(row.get("timestamp")),
        "open": open_p,
        "high": high_p,
        "low": low_p,
        "close": close_p,
        "volume": volume,
    }


def _volume_ratio(bars: list[dict[str, Any]], lookback: int = 20) -> float | None:
    if len(bars) < 3:
        return None
    recent = bars[-min(len(bars), lookback):]
    current_volume = num(recent[-1].get("volume"))
    previous = [num(b.get("volume")) for b in recent[:-1] if num(b.get("volume")) > 0]
    if current_volume <= 0 or not previous:
        return None
    avg = statistics.mean(previous)
    if avg <= 0:
        return None
    return current_volume / avg


def _scenario_threshold(scenario_id: str, default_window: int) -> tuple[int, float]:
    scenario = scenario_id.lower()
    if "or30" in scenario:
        return 30, 1.3
    if "or10" in scenario:
        return 10, 1.5
    return default_window, 1.5 if default_window == 10 else 1.3


def evaluate_watchlist_item(
    item: dict[str, Any],
    *,
    trading_date: str,
    default_window: int,
    max_lag_minutes: float,
    row_limit: int,
    emit_watch: bool,
    now_kst: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    stock_code = str(item.get("stock_code") or "")
    stock_name = item.get("stock_name")
    rows, load_error = load_snapshot_rows(stock_code, trading_date, row_limit)
    bars = [b for r in rows if (b := _clean_bar(r)) is not None]
    eval_summary: dict[str, Any] = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "snapshot_rows": len(rows),
        "valid_bars": len(bars),
        "events": 0,
        "blocking_conditions": [],
    }
    if load_error:
        eval_summary["blocking_conditions"].append(f"snapshot_1m_query_failed:{load_error}")
        return [], eval_summary
    if not bars:
        eval_summary["blocking_conditions"].append("snapshot_1m_bars_not_accumulated")
        return [], eval_summary

    latest = bars[-1]
    latest_ts = latest.get("timestamp")
    if not isinstance(latest_ts, datetime):
        eval_summary["blocking_conditions"].append("latest_snapshot_timestamp_invalid")
        return [], eval_summary
    lag_minutes = max((now_kst - latest_ts).total_seconds() / 60.0, 0.0)
    volume_ratio = _volume_ratio(bars)
    events: list[dict[str, Any]] = []
    scenarios = item.get("entry_scenarios", []) if isinstance(item.get("entry_scenarios"), list) else []
    if not scenarios:
        scenarios = [{"scenario_id": f"or{default_window}_breakout", "label": f"OR{default_window} 상단 돌파"}]

    for scenario in scenarios:
        scenario_id = str(scenario.get("scenario_id") or f"or{default_window}_breakout")
        window, vol_threshold = _scenario_threshold(scenario_id, default_window)
        if window != default_window:
            # A single run should evaluate one window to keep n8n stage semantics clear.
            continue
        if len(bars) < window:
            eval_summary["blocking_conditions"].append(f"snapshot_1m_insufficient_rows_for_or{window}")
            continue

        opening_bars = bars[:window]
        or_high = max(num(b.get("high")) for b in opening_bars)
        or_low = min(num(b.get("low")) for b in opening_bars)
        current_price = num(latest.get("close"))
        breakout_pct = ((current_price - or_high) / or_high * 100.0) if or_high > 0 else None
        breakout = bool(breakout_pct is not None and breakout_pct > 0)
        near_breakout = bool(breakout_pct is not None and -0.20 <= breakout_pct <= 0)
        volume_ok = volume_ratio is not None and volume_ratio >= vol_threshold
        lag_ok = lag_minutes <= max_lag_minutes

        should_emit = breakout and lag_ok and (volume_ok or emit_watch)
        watch_emit = emit_watch and (near_breakout or (breakout and not volume_ok) or not lag_ok)
        if not should_emit and not watch_emit:
            continue

        breakout_score = 25.0 if breakout else (10.0 if near_breakout else 0.0)
        volume_score = 20.0 if volume_ok else (8.0 if volume_ratio is not None and volume_ratio >= 1.0 else 0.0)
        lag_score = 10.0 if lag_ok else -10.0
        watchlist_score = num(item.get("candidate_score"))
        confidence = max(0.0, min(100.0, watchlist_score * 0.45 + breakout_score + volume_score + lag_score))
        event_type = "ENTRY_TIMING_CANDIDATE" if should_emit else "WATCH"
        signal_type = "WATCH"
        event_blocks = list(dict.fromkeys(ORDER_BLOCKERS + ([] if lag_ok else ["snapshot_lag_too_high"])))
        event_id = f"{latest_ts.strftime('%Y%m%dT%H%M%S')}_{stock_code}_or{window}_breakout"
        risk_controls = dict(item.get("risk_controls") or {})
        risk_controls.update(
            {
                "suggested_mode": "alert_only",
                "suggested_budget_krw": 0,
                "paper_order_allowed": False,
                "real_order_allowed": False,
            }
        )
        message = (
            f"{stock_code} {stock_name or ''} OR{window} "
            f"{'상단 돌파 후보' if breakout else '근접 관찰 후보'}. "
            "현재는 alert-only; paper/real 주문 금지."
        ).strip()
        event = {
            "event_id": event_id,
            "stock_code": stock_code,
            "stock_name": stock_name,
            "scenario_id": scenario_id,
            "window_minutes": window,
            "event_type": event_type,
            "signal_type": signal_type,
            "confidence_score": round(confidence, 4),
            "current_snapshot": {
                "timestamp": latest_ts.isoformat(timespec="seconds"),
                "current_price": current_price,
                "open": latest.get("open"),
                "high": latest.get("high"),
                "low": latest.get("low"),
                "close": latest.get("close"),
                "volume": latest.get("volume"),
                "snapshot_lag_minutes": round(lag_minutes, 4),
            },
            "opening_range": {
                "or_high": or_high,
                "or_low": or_low,
                "breakout_pct": round(breakout_pct, 4) if breakout_pct is not None else None,
            },
            "volume_context": {
                "volume_ratio": round(volume_ratio, 4) if volume_ratio is not None else None,
                "volume_reference": "recent_snapshot_average",
                "volume_threshold": vol_threshold,
            },
            "score_details": {
                "watchlist_score": watchlist_score,
                "breakout_score": breakout_score,
                "volume_score": volume_score,
                "lag_score": lag_score,
                "thresholds": {
                    "breakout_pct_min": 0,
                    "near_breakout_pct_min": -0.20,
                    "volume_ratio_min": vol_threshold,
                    "max_lag_minutes": max_lag_minutes,
                },
            },
            "risk_controls": risk_controls,
            "blocking_conditions": event_blocks,
            "message": message,
        }
        events.append(event)

    eval_summary["events"] = len(events)
    return events, eval_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", type=int, choices=[10, 30], default=10)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--row-limit", type=int, default=500)
    parser.add_argument("--trading-date", default=None, help="KST YYYY-MM-DD; default today")
    parser.add_argument("--max-lag-minutes", type=float, default=10.0)
    parser.add_argument("--emit-watch", action="store_true", help="Also emit near-breakout / partial-condition WATCH events")
    parser.add_argument("--allow-empty-watchlist", action="store_true", help="Return completed with 0 events instead of blocked when watchlist is empty")
    args = parser.parse_args()

    now_kst = datetime.now(KST)
    trading_date = args.trading_date or now_kst.date().isoformat()
    generated_at = now_kst.isoformat(timespec="seconds")
    blocks: list[str] = []
    alerts: list[str] = []

    watchlist, watchlist_payload, watch_blocks, watch_alerts = load_today_watchlist(args.limit)
    alerts.extend(watch_alerts)
    if watch_blocks and not watchlist and not args.allow_empty_watchlist:
        blocks.extend(watch_blocks)
    if not watchlist and not args.allow_empty_watchlist:
        blocks.append("today_watchlist_empty")

    timing_events: list[dict[str, Any]] = []
    evaluated: list[dict[str, Any]] = []
    if watchlist:
        for item in watchlist:
            events, summary = evaluate_watchlist_item(
                item,
                trading_date=trading_date,
                default_window=args.window,
                max_lag_minutes=args.max_lag_minutes,
                row_limit=args.row_limit,
                emit_watch=args.emit_watch,
                now_kst=now_kst,
            )
            evaluated.append(summary)
            timing_events.extend(events)

    data_blocks = []
    for summary in evaluated:
        data_blocks.extend(str(x) for x in summary.get("blocking_conditions", []) if x)
    if evaluated and all(num(s.get("valid_bars")) <= 0 for s in evaluated):
        blocks.append("snapshot_1m_bars_not_accumulated_for_watchlist")
    alerts.extend(list(dict.fromkeys(data_blocks))[:20])

    alert_messages = [e.get("message") for e in timing_events if e.get("message")]
    alerts.extend(str(x) for x in alert_messages[:10])

    out = {
        "ok": not blocks,
        "workflow": WORKFLOW,
        "stage": STAGE,
        "status": "completed" if not blocks else "blocked",
        "generated_at": generated_at,
        "trading_date": trading_date,
        "summary": {
            "window_minutes": args.window,
            "watchlist_count": len(watchlist),
            "evaluated_count": len(evaluated),
            "alert_count": len(timing_events),
            "paper_candidate_count": 0,
            "order_execution_enabled": False,
            "source": SNAPSHOT_SOURCE,
            "time_frame": SNAPSHOT_TIME_FRAME,
            "max_lag_minutes": args.max_lag_minutes,
            "today_watchlist_status": watchlist_payload.get("status") if isinstance(watchlist_payload, dict) else None,
        },
        "evaluated": evaluated,
        "timing_events": timing_events,
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts,
        "next_actions": [
            "Telegram/WebUI에는 timing_events의 message와 blocking_conditions만 요약 전송하세요.",
            "이 stage는 alert-only입니다. paper/real 주문은 별도 Leader 승인 workflow 전까지 계속 금지하세요.",
            "반복적으로 놓친 타이밍은 daily_pnl_feedback_report의 strategy_change_candidates로 승격하세요.",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
