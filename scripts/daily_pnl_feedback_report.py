"""Daily PnL and execution feedback report for n8n/Hermes.

Uses Supabase REST with service-role key when available. Values are aggregated
only; secrets are never printed. If tables/data are missing, emits explicit
blocking_conditions instead of fake metrics.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

SNAPSHOT_SOURCE = "kiwoom_ka10006_snapshot"
SNAPSHOT_TIME_FRAME = "snapshot_1m"


def read_env() -> dict[str, str]:
    env_path = PROJECT_ROOT / ".env"
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for raw in env_path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.split(" #", 1)[0].strip().strip('"').strip("'")
    return out


def rest_get(env: dict[str, str], table: str, params: dict[str, str] | None = None) -> tuple[bool, Any, str | None]:
    url = env.get("SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_ANON_KEY")
    if not url or not key:
        return False, None, "missing_supabase_url_or_key"
    query = urlencode(params or {})
    endpoint = f"{url}/rest/v1/{table}" + (f"?{query}" if query else "")
    req = Request(
        endpoint,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Prefer": "count=exact",
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return True, json.loads(body) if body else [], None
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[-1000:]
        return False, None, f"http_{exc.code}_{table}: {body}"
    except URLError as exc:
        return False, None, f"url_error_{table}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}_{table}: {exc}"


def num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def summarize_snapshot_1m(env: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    """Summarize snapshot_1m accumulation for the daily feedback report.

    Early Phase 1/2 data scarcity is expected, so the caller decides which
    snapshot blocks should make the report itself blocked.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
    ok, rows, err = rest_get(
        env,
        "intraday_prices",
        {
            "select": "stock_code,timestamp,time_frame,source,open,high,low,close,volume",
            "time_frame": f"eq.{SNAPSHOT_TIME_FRAME}",
            "source": f"eq.{SNAPSHOT_SOURCE}",
            "timestamp": f"gte.{since}",
            "order": "timestamp.desc",
            "limit": "5000",
        },
    )
    blocks: list[str] = []
    if not ok:
        blocks.append(err or "snapshot_1m_query_failed")
        return {
            "ok": False,
            "source": SNAPSHOT_SOURCE,
            "time_frame": SNAPSHOT_TIME_FRAME,
            "rows": 0,
            "active_codes": 0,
            "latest_timestamp": None,
            "latest_lag_minutes": None,
            "quality_error_counts": {},
            "blocking_conditions": blocks,
        }, blocks

    rows = rows if isinstance(rows, list) else []
    codes: set[str] = set()
    latest_ts: datetime | None = None
    quality_errors: dict[str, int] = {}
    seen_keys: set[tuple[str, str]] = set()
    duplicates = 0

    for row in rows:
        code = str(row.get("stock_code") or "")
        ts_text = str(row.get("timestamp") or "")
        if code:
            codes.add(code)
        key = (code, ts_text)
        if key in seen_keys:
            duplicates += 1
        seen_keys.add(key)
        ts = parse_ts(ts_text)
        if ts and (latest_ts is None or ts > latest_ts):
            latest_ts = ts
        open_p, high_p, low_p, close_p = (num(row.get(k)) for k in ("open", "high", "low", "close"))
        if min(open_p, high_p, low_p, close_p) <= 0:
            quality_errors["non_positive_ohlc"] = quality_errors.get("non_positive_ohlc", 0) + 1
        elif high_p < max(open_p, close_p) or low_p > min(open_p, close_p):
            quality_errors["ohlc_structure_bad"] = quality_errors.get("ohlc_structure_bad", 0) + 1
        if ts is None:
            quality_errors["invalid_timestamp"] = quality_errors.get("invalid_timestamp", 0) + 1

    latest_lag_minutes = None
    if latest_ts:
        latest_lag_minutes = round((datetime.now(timezone.utc) - latest_ts.astimezone(timezone.utc)).total_seconds() / 60, 2)

    if len(rows) < 20:
        blocks.append("snapshot_1m_rows_below_daily_feedback_minimum")
    if len(codes) < 5:
        blocks.append("snapshot_1m_active_codes_below_daily_feedback_minimum")
    if latest_ts is None:
        blocks.append("snapshot_1m_latest_timestamp_missing")
    if quality_errors:
        blocks.append("snapshot_1m_quality_errors_detected")

    return {
        "ok": not blocks,
        "source": SNAPSHOT_SOURCE,
        "time_frame": SNAPSHOT_TIME_FRAME,
        "lookback_days": 2,
        "rows": len(rows),
        "active_codes": len(codes),
        "latest_timestamp": latest_ts.isoformat() if latest_ts else None,
        "latest_lag_minutes": latest_lag_minutes,
        "duplicate_stock_timestamp_keys": duplicates,
        "quality_error_counts": dict(sorted(quality_errors.items())),
        "blocking_conditions": blocks,
    }, blocks


def run_json_command(args: list[str], timeout: int = 180) -> tuple[dict[str, Any] | None, str | None, int]:
    """Run a local JSON-producing workflow script without fabricating results."""
    try:
        proc = subprocess.run(
            args,
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}", 2
    stdout = (proc.stdout or "").strip()
    try:
        data = json.loads(stdout) if stdout else None
    except json.JSONDecodeError:
        return None, (proc.stderr or stdout)[-1500:], proc.returncode
    return data if isinstance(data, dict) else None, proc.stderr[-1500:] if proc.stderr else None, proc.returncode


def derive_missed_timing_events(evaluated: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create evidence-only missed timing candidates from evaluated summaries."""
    out: list[dict[str, Any]] = []
    event_codes = {str(e.get("stock_code")) for e in events if e.get("stock_code")}
    today = datetime.now(timezone.utc).date().isoformat()
    for item in evaluated:
        code = str(item.get("stock_code") or "")
        blocks = [str(x) for x in item.get("blocking_conditions", []) if x]
        valid_bars = int(num(item.get("valid_bars")))
        if not code or code in event_codes:
            continue
        if any("insufficient_rows" in b or "not_accumulated" in b for b in blocks):
            out.append(
                {
                    "event_id": f"{today}_{code}_missed_due_to_snapshot_insufficient",
                    "stock_code": code,
                    "missed_type": "evaluation_blocked",
                    "evidence": {"valid_bars": valid_bars, "blocking_conditions": blocks},
                    "root_cause_candidates": ["snapshot_1m_accumulation_insufficient"],
                    "strategy_change_candidate": "수집 rows가 OR10/OR30 평가 조건을 충족하는지 장중 수집 주기/대상 종목을 점검",
                }
            )
        elif any("lag" in b for b in blocks):
            out.append(
                {
                    "event_id": f"{today}_{code}_missed_due_to_snapshot_lag",
                    "stock_code": code,
                    "missed_type": "late_data",
                    "evidence": {"blocking_conditions": blocks},
                    "root_cause_candidates": ["snapshot_lag_too_high"],
                    "strategy_change_candidate": "장중 수집/알림 cron 간격과 runner 지연 원인 점검",
                }
            )
    return out[:20]


def summarize_intraday_timing_alerts() -> tuple[dict[str, Any], list[str]]:
    """Run OR10/OR30 alert stages in report-safe mode and summarize output."""
    windows: dict[str, Any] = {}
    blocks: list[str] = []
    total_alerts = 0
    total_evaluated = 0
    all_events: list[dict[str, Any]] = []
    all_eval: list[dict[str, Any]] = []
    for window in (10, 30):
        data, err, rc = run_json_command(
            [
                sys.executable,
                "scripts/run_intraday_timing_alerts.py",
                "--window",
                str(window),
                "--limit",
                "10",
                "--allow-empty-watchlist",
            ],
            timeout=240,
        )
        key = f"or{window}"
        if data is None:
            block = f"intraday_timing_alert_{window}m_invalid_json"
            blocks.append(block)
            windows[key] = {"ok": False, "blocking_conditions": [block], "error_tail": err, "returncode": rc}
            continue
        summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
        events = data.get("timing_events") if isinstance(data.get("timing_events"), list) else []
        evaluated = data.get("evaluated") if isinstance(data.get("evaluated"), list) else []
        payload_blocks = [str(x) for x in data.get("blocking_conditions", []) if x]
        total_alerts += len(events)
        total_evaluated += len(evaluated)
        all_events.extend(e for e in events if isinstance(e, dict))
        all_eval.extend(e for e in evaluated if isinstance(e, dict))
        windows[key] = {
            "ok": bool(data.get("ok")),
            "status": data.get("status"),
            "summary": summary,
            "event_count": len(events),
            "evaluated_count": len(evaluated),
            "blocking_conditions": payload_blocks,
            "alerts": data.get("alerts", [])[:10] if isinstance(data.get("alerts"), list) else [],
            "timing_events": events[:10],
        }
        blocks.extend(payload_blocks)

    missed_timing_events = derive_missed_timing_events(all_eval, all_events)
    return {
        "ok": not blocks,
        "mode": "report_safe_replay",
        "windows": windows,
        "total_evaluated_count": total_evaluated,
        "total_timing_event_count": total_alerts,
        "missed_timing_event_count": len(missed_timing_events),
        "missed_timing_events": missed_timing_events,
        "blocking_conditions": list(dict.fromkeys(blocks)),
    }, blocks


def derive_strategy_change_candidates(
    *,
    signals: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    snapshot_status: dict[str, Any],
    intraday_status: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate review candidates only; never auto-approve code/threshold changes."""
    candidates: list[dict[str, Any]] = []
    today = datetime.now(timezone.utc).date().isoformat()
    signal_counts: dict[str, int] = {}
    for sig in signals:
        st = str(sig.get("signal_type") or "UNKNOWN")
        signal_counts[st] = signal_counts.get(st, 0) + 1

    if not signals:
        candidates.append(
            {
                "candidate_id": f"{today}_no_today_signals_review",
                "source": "daily_pnl_feedback_report",
                "strategy_id": "candidate_compression_layer",
                "problem_observed": "오늘 trading_signals가 없어 today_watchlist와 intraday timing 평가가 비어 있음",
                "evidence": {"today_signal_count": 0, "intraday_timing_event_count": intraday_status.get("total_timing_event_count")},
                "proposed_change": {
                    "change_type": "data_or_signal_pipeline_review",
                    "field": "morning_signal_generation",
                    "current_value": "no_today_signals",
                    "proposed_value": "원인 분류: 데이터 부재/임계값 과도/시장 조건 부적합 중 무엇인지 분리",
                },
                "validation_required": ["실제 morning signal 입력 데이터 확인", "임계값 변경 전 백테스트"],
                "status": "candidate_only",
                "approved_for_code_change": False,
            }
        )

    if signals and not orders:
        candidates.append(
            {
                "candidate_id": f"{today}_signals_without_orders_review",
                "source": "daily_pnl_feedback_report",
                "strategy_id": "leader_approval_order_workflow_v1",
                "problem_observed": "신호는 있으나 오늘 주문 기록이 없음",
                "evidence": {"today_signal_counts": signal_counts, "today_order_count": 0},
                "proposed_change": {
                    "change_type": "workflow_gate_review",
                    "field": "leader_approval_or_paper_order_gate",
                    "current_value": "orders_empty",
                    "proposed_value": "승인형 paper 주문 단계의 blocker/미연결 여부 점검",
                },
                "validation_required": ["paper-only forward test", "Leader approval workflow smoke test"],
                "status": "candidate_only",
                "approved_for_code_change": False,
            }
        )

    missed_count = int(num(intraday_status.get("missed_timing_event_count")))
    if missed_count > 0:
        candidates.append(
            {
                "candidate_id": f"{today}_missed_timing_operational_review",
                "source": "daily_pnl_feedback_report",
                "strategy_id": "intraday_timing_alert_v1",
                "problem_observed": "장중 타이밍 평가가 데이터 부족 또는 지연으로 차단된 후보가 있음",
                "evidence": {
                    "missed_timing_event_count": missed_count,
                    "sample_events": intraday_status.get("missed_timing_events", [])[:5],
                },
                "proposed_change": {
                    "change_type": "operational_monitoring_adjustment",
                    "field": "snapshot_collection_and_alert_schedule",
                    "current_value": "alert evaluation blocked for some watchlist items",
                    "proposed_value": "수집 주기/대상/lag 기준 점검; 전략 threshold 변경은 보류",
                },
                "validation_required": ["snapshot_1m quality report", "paper-only forward observation"],
                "status": "candidate_only",
                "approved_for_code_change": False,
            }
        )

    snapshot_blocks = snapshot_status.get("blocking_conditions", []) if isinstance(snapshot_status.get("blocking_conditions"), list) else []
    if any("quality" in str(b) for b in snapshot_blocks):
        candidates.append(
            {
                "candidate_id": f"{today}_snapshot_quality_review",
                "source": "daily_pnl_feedback_report",
                "strategy_id": "snapshot_1m_data_pipeline",
                "problem_observed": "snapshot_1m 품질 이상이 감지됨",
                "evidence": {"snapshot_1m_accumulation": snapshot_status},
                "proposed_change": {
                    "change_type": "data_pipeline_fix",
                    "field": "snapshot_1m_quality_guard",
                    "current_value": "quality_errors_detected",
                    "proposed_value": "전략 변경보다 데이터 수집/정제 오류 우선 해결",
                },
                "validation_required": ["inspect_snapshot_1m_status.py", "py_compile and runner smoke"],
                "status": "candidate_only",
                "approved_for_code_change": False,
            }
        )
    return candidates


def main() -> int:
    env = read_env()
    today = datetime.now(timezone.utc).date().isoformat()
    blocking: list[str] = []
    alerts: list[str] = []

    ok_pos, positions, err_pos = rest_get(env, "positions", {"select": "stock_code,quantity,avg_price,current_price,pnl,pnl_pct,realized_pnl,status,strategy", "quantity": "gt.0"})
    if not ok_pos:
        blocking.append(err_pos or "positions_query_failed")
        positions = []

    ok_orders, orders, err_orders = rest_get(env, "orders", {"select": "stock_code,order_type,quantity,price,filled_price,filled_quantity,status,strategy,created_at", "created_at": f"gte.{today}T00:00:00Z", "order": "created_at.desc"})
    if not ok_orders:
        blocking.append(err_orders or "orders_query_failed")
        orders = []

    ok_signals, signals, err_signals = rest_get(env, "trading_signals", {"select": "stock_code,signal_type,score,strategy,executed,signal_date,score_details", "signal_date": f"gte.{today}T00:00:00Z", "order": "signal_date.desc"})
    if not ok_signals:
        blocking.append(err_signals or "trading_signals_query_failed")
        signals = []

    snapshot_status, snapshot_blocks = summarize_snapshot_1m(env)
    # Snapshot accumulation is included for visibility. Expected early scarcity
    # should not fail the PnL report; quality/query failures should.
    snapshot_hard_blocks = [
        b for b in snapshot_blocks
        if "quality_errors" in b or "query_failed" in b or "latest_timestamp_missing" in b
    ]
    blocking.extend(snapshot_hard_blocks)

    intraday_status, intraday_blocks = summarize_intraday_timing_alerts()
    # Intraday alert replay is feedback context. Empty watchlist and data scarcity
    # become strategy candidates, not hard failures of the PnL report.
    intraday_hard_blocks = [b for b in intraday_blocks if "invalid_json" in b or "query_failed" in b]
    blocking.extend(intraday_hard_blocks)

    open_positions = [p for p in positions if num(p.get("quantity")) > 0]
    total_unrealized = sum(num(p.get("pnl")) for p in open_positions)
    total_realized = sum(num(p.get("realized_pnl")) for p in open_positions)
    avg_pnl_pct = sum(num(p.get("pnl_pct")) for p in open_positions) / len(open_positions) if open_positions else 0.0

    order_counts: dict[str, int] = {}
    for order in orders:
        status = str(order.get("status") or "UNKNOWN")
        order_counts[status] = order_counts.get(status, 0) + 1

    signal_counts: dict[str, int] = {}
    executed_count = 0
    for sig in signals:
        st = str(sig.get("signal_type") or "UNKNOWN")
        signal_counts[st] = signal_counts.get(st, 0) + 1
        if sig.get("executed"):
            executed_count += 1

    if not signals:
        blocking.append("no_today_signals_found")
    if not orders:
        alerts.append("today_orders_empty_or_not_recorded")

    strategy_change_candidates = derive_strategy_change_candidates(
        signals=signals,
        orders=orders,
        snapshot_status=snapshot_status,
        intraday_status=intraday_status,
    )

    report = {
        "ok": not blocking,
        "workflow": "daily_trading_workflow_v1",
        "stage": "daily_pnl_feedback_report",
        "status": "completed" if not blocking else "blocked",
        "date_utc": today,
        "summary": {
            "open_position_count": len(open_positions),
            "total_unrealized_pnl": round(total_unrealized, 2),
            "total_realized_pnl_from_positions": round(total_realized, 2),
            "avg_open_pnl_pct": round(avg_pnl_pct, 4),
            "today_order_count": len(orders),
            "today_order_status_counts": order_counts,
            "today_signal_count": len(signals),
            "today_signal_counts": signal_counts,
            "today_executed_signal_count": executed_count,
            "snapshot_1m_accumulation": snapshot_status,
            "intraday_timing_alert_summary": {
                "mode": intraday_status.get("mode"),
                "total_evaluated_count": intraday_status.get("total_evaluated_count"),
                "total_timing_event_count": intraday_status.get("total_timing_event_count"),
                "missed_timing_event_count": intraday_status.get("missed_timing_event_count"),
                "blocking_conditions": intraday_status.get("blocking_conditions", []),
            },
            "strategy_change_candidate_count": len(strategy_change_candidates),
        },
        "top_open_positions": sorted(open_positions, key=lambda p: num(p.get("pnl")), reverse=True)[:10],
        "recent_orders": orders[:10],
        "recent_signals": signals[:10],
        "intraday_timing_alerts": intraday_status,
        "missed_timing_events": intraday_status.get("missed_timing_events", []),
        "strategy_change_candidates": strategy_change_candidates,
        "blocking_conditions": list(dict.fromkeys(blocking)),
        "alerts": alerts,
        "feedback_questions": [
            "BUY 신호 대비 실제 주문이 발생했는가?",
            "미실행 사유가 데이터/리스크/API/점수 중 어디에 집중되는가?",
            "손절/익절이 계획된 수치대로 작동했는가?",
            "다음 거래일에 임계값/가중치 조정 후보가 있는가?",
            "snapshot_1m 누적 rows/active_codes/latest_lag가 백테스트 준비 기준에 가까워지고 있는가?",
            "intraday_timing_alert가 발생/차단된 원인은 watchlist 부재, snapshot 부족, lag, threshold 중 무엇인가?",
            "strategy_change_candidates 중 백테스트 없이 즉시 반영하려는 항목은 없는가?",
        ],
        "storage_policy": "Daily PnL details belong in DB/reports, not durable memory; reusable lessons go to skills or compact memory.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
