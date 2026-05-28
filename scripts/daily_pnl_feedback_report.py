"""Daily PnL and execution feedback report for n8n/Hermes.

Uses Supabase REST with service-role key when available. Values are aggregated
only; secrets are never printed. If tables/data are missing, emits explicit
blocking_conditions instead of fake metrics.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


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
        },
        "top_open_positions": sorted(open_positions, key=lambda p: num(p.get("pnl")), reverse=True)[:10],
        "recent_orders": orders[:10],
        "recent_signals": signals[:10],
        "blocking_conditions": list(dict.fromkeys(blocking)),
        "alerts": alerts,
        "feedback_questions": [
            "BUY 신호 대비 실제 주문이 발생했는가?",
            "미실행 사유가 데이터/리스크/API/점수 중 어디에 집중되는가?",
            "손절/익절이 계획된 수치대로 작동했는가?",
            "다음 거래일에 임계값/가중치 조정 후보가 있는가?",
        ],
        "storage_policy": "Daily PnL details belong in DB/reports, not durable memory; reusable lessons go to skills or compact memory.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
