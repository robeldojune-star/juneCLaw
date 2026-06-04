"""Collect current-session Kiwoom ka10006 snapshots into intraday_prices.

This is the safe replacement path after ka10005 proved to be daily-like rather
than minute-like. It stores one row per stock per KST minute with
source=kiwoom_ka10006_snapshot and time_frame=snapshot_1m.

Real data only: if candidates/master data/API are unavailable, report explicit
blocking_conditions. No synthetic rows are generated.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.kiwoom_client import KiwoomAPIClient, clean_int  # noqa: E402
from core.market_data_service import MarketDataService, normalize_stock_code  # noqa: E402
from core.supabase_rest import SupabaseRestClient, SupabaseRestError  # noqa: E402
from core.trading_mode import load_env, redacted_mode_dict, resolve_execution_mode  # noqa: E402


WORKFLOW = "daily_trading_workflow_v1"
STAGE = "collect_current_session_snapshots"


def _is_kiwoom_snapshot_code(code: str | None) -> bool:
    """ka10006 currently accepts standard six-digit numeric stock/ETF codes."""
    return bool(code and len(code) == 6 and code.isdigit())


def _run_candidate_compression() -> dict[str, Any] | None:
    proc = subprocess.run(
        [sys.executable, "scripts/candidate_compression_layer.py"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def _load_codes_from_supabase(limit: int) -> tuple[list[str], list[str], list[str]]:
    """Return (codes, alerts, blocks) from real DB sources."""
    alerts: list[str] = []
    blocks: list[str] = []
    codes: list[str] = []
    try:
        sb = SupabaseRestClient()
    except SupabaseRestError as exc:
        return [], [], [str(exc)]

    comp = _run_candidate_compression()
    if comp and isinstance(comp.get("candidates"), list):
        for c in comp.get("candidates", []):
            code = normalize_stock_code(c.get("stock_code"))
            if code and not _is_kiwoom_snapshot_code(code):
                alerts.append(f"skipped_non_numeric_snapshot_code:{code}")
                continue
            if code and code not in codes:
                codes.append(code)
            if len(codes) >= limit:
                break
    else:
        alerts.append("candidate_compression_unavailable_for_snapshot_collection")

    if not codes:
        try:
            rows = sb.get(
                "kospi_top50",
                {
                    "select": "stock_code,rank,is_active",
                    "is_active": "eq.true",
                    "order": "rank.asc",
                    "limit": str(limit),
                },
                timeout=20,
            )
            for r in rows:
                code = normalize_stock_code(r.get("stock_code"))
                if code and not _is_kiwoom_snapshot_code(code):
                    alerts.append(f"skipped_non_numeric_snapshot_code:{code}")
                    continue
                if code and code not in codes:
                    codes.append(code)
        except SupabaseRestError as exc:
            alerts.append(f"kospi_top50_fallback_failed:{exc}")

    if not codes:
        blocks.append("no_real_stock_codes_for_snapshot_collection")
    return codes[:limit], alerts, blocks


def _minute_timestamp(now_kst: datetime) -> str:
    minute = now_kst.replace(second=0, microsecond=0)
    return minute.isoformat()


def _snapshot_payload(code: str, snap: dict[str, Any], timestamp: str) -> tuple[dict[str, Any] | None, str | None]:
    open_p = clean_int(snap.get("open_pric"), abs_value=True)
    high_p = clean_int(snap.get("high_pric"), abs_value=True)
    low_p = clean_int(snap.get("low_pric"), abs_value=True)
    close_p = clean_int(snap.get("close_pric"), abs_value=True) or clean_int(snap.get("cur_prc"), abs_value=True)
    volume = clean_int(snap.get("trde_qty"), abs_value=True)
    trading_value = clean_int(snap.get("trde_prica"), abs_value=True)
    if open_p is None or high_p is None or low_p is None or close_p is None:
        return None, "invalid_ohlc_snapshot"
    if any(v < 0 for v in [open_p, high_p, low_p, close_p]):
        return None, "invalid_ohlc_snapshot"
    if high_p < max(open_p, close_p) or low_p > min(open_p, close_p):
        return None, "ohlc_structure_bad_snapshot"
    row = {
        "stock_code": code,
        "timestamp": timestamp,
        "time_frame": "snapshot_1m",
        "open": open_p,
        "high": high_p,
        "low": low_p,
        "close": close_p,
        "volume": volume,
        "trading_value": trading_value,
        "source": "kiwoom_ka10006_snapshot",
    }
    return row, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-codes", nargs="+", default=None)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--trading-env", choices=["mock", "prod"], default=None, help="Kiwoom env for current-session snapshots. Defaults to LIVE_DATA_KIWOOM_ENV/TRADING_ENV/mock.")
    parser.add_argument("--allow-offhours", action="store_true")
    args = parser.parse_args()

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    hhmm = now_kst.hour * 100 + now_kst.minute
    market_hours = 900 <= hhmm <= 1535 and now_kst.weekday() < 5
    blocks: list[str] = []
    alerts: list[str] = []
    mode = resolve_execution_mode(purpose="collect_current_session_snapshots", requested_env=args.trading_env, env=load_env(PROJECT_ROOT / ".env"))
    if not mode.can_collect_live_snapshot:
        blocks.append("live_snapshot_collection_mode_not_allowed")

    if args.stock_codes:
        codes = []
        for c in args.stock_codes:
            code = normalize_stock_code(c)
            if code and not _is_kiwoom_snapshot_code(code):
                alerts.append(f"skipped_non_numeric_snapshot_code:{code}")
                continue
            if code and code not in codes:
                codes.append(code)
        codes = codes[: args.limit]
    else:
        codes, load_alerts, load_blocks = _load_codes_from_supabase(args.limit)
        alerts.extend(load_alerts)
        blocks.extend(load_blocks)

    if not market_hours and not args.allow_offhours:
        blocks.append("outside_market_hours_for_current_session_snapshot")

    try:
        sb = SupabaseRestClient()
    except SupabaseRestError as exc:
        blocks.append(str(exc))
        sb = None

    payload: list[dict[str, Any]] = []
    fetch_errors: list[str] = []
    timestamp = _minute_timestamp(now_kst)
    if not blocks:
        client = KiwoomAPIClient.from_env(PROJECT_ROOT / ".env", trading_env=mode.kiwoom_env)
        market = MarketDataService(client)
        for idx, code in enumerate(codes):
            if idx and args.delay > 0:
                time.sleep(args.delay)
            try:
                snap = market.get_current_session_snapshot(code)
            except Exception as exc:  # noqa: BLE001
                fetch_errors.append(f"{code}:{type(exc).__name__}")
                continue
            row, err = _snapshot_payload(code, snap, timestamp)
            if err:
                fetch_errors.append(f"{code}:{err}")
                continue
            payload.append(row)

    inserted: list[dict[str, Any]] = []
    if payload and sb is not None:
        try:
            inserted = sb.upsert_rows("intraday_prices", payload, on_conflict="stock_code,timestamp,time_frame", timeout=30)
        except SupabaseRestError as exc:
            blocks.append(f"snapshot_upsert_failed:{exc}")

    if fetch_errors:
        alerts.extend(fetch_errors[:20])
    if not payload and not blocks:
        blocks.append("no_valid_snapshot_payload_rows")

    out = {
        "ok": not blocks,
        "workflow": WORKFLOW,
        "stage": STAGE,
        "status": "completed" if not blocks else "blocked",
        "generated_at": datetime.now(ZoneInfo("UTC")).isoformat(timespec="seconds"),
        "summary": {
            "timestamp_kst_minute": timestamp,
            "execution_mode": redacted_mode_dict(mode),
            "market_hours": market_hours,
            "requested_stock_count": len(codes),
            "payload_rows": len(payload),
            "upserted_rows": len(inserted),
            "time_frame": "snapshot_1m",
            "source": "kiwoom_ka10006_snapshot",
        },
        "stock_codes": codes,
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts,
        "next_actions": [
            "장중 1분~5분 간격으로 반복 실행해 intraday_prices snapshot_1m을 누적하세요",
            "90일 백테스트는 snapshot_1m 누적 기간이 충분해질 때까지 blocked가 정상입니다",
            "실주문은 Leader 승인형 paper-only 검증 전까지 활성화하지 마세요",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
