"""Collect verified historical minute bars via Kiwoom ka10080 into Supabase.

Real-data-first rules:
- Uses ka10080 주식분봉차트조회요청, not ka10005.
- Stores source=kiwoom_ka10080_minute and time_frame=1min by default.
- No synthetic rows are created. Invalid/missing timestamp or OHLC rows are skipped
  and reported as alerts/blocking conditions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
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
STAGE = "collect_intraday_90d"
SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"


def _parse_cntr_tm(raw: dict[str, Any]) -> datetime | None:
    digits = re.sub(r"\D", "", str(raw.get("cntr_tm") or ""))
    if len(digits) < 12:
        return None
    digits = digits[:14] if len(digits) >= 14 else digits[:12] + "00"
    try:
        return datetime.strptime(digits, "%Y%m%d%H%M%S").replace(tzinfo=ZoneInfo("Asia/Seoul"))
    except ValueError:
        return None


def _row_to_payload(code: str, raw: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None, datetime | None]:
    ts = _parse_cntr_tm(raw)
    if ts is None:
        return None, "missing_or_invalid_cntr_tm", None
    open_p = clean_int(raw.get("open_pric"), abs_value=True)
    high_p = clean_int(raw.get("high_pric"), abs_value=True)
    low_p = clean_int(raw.get("low_pric"), abs_value=True)
    close_p = clean_int(raw.get("cur_prc"), abs_value=True) or clean_int(raw.get("close_pric"), abs_value=True)
    volume = clean_int(raw.get("trde_qty"), abs_value=True)
    if open_p is None or high_p is None or low_p is None or close_p is None:
        return None, "missing_ohlc", ts
    if min(open_p, high_p, low_p, close_p) <= 0:
        return None, "non_positive_ohlc", ts
    if high_p < max(open_p, close_p) or low_p > min(open_p, close_p):
        return None, "ohlc_structure_bad", ts
    return {
        "stock_code": code,
        "timestamp": ts.isoformat(),
        "time_frame": TIME_FRAME,
        "open": open_p,
        "high": high_p,
        "low": low_p,
        "close": close_p,
        "volume": volume,
        "trading_value": None,
        "source": SOURCE,
    }, None, ts


def _next_base_dt(oldest: datetime | None, fallback: datetime) -> str:
    base = (oldest or fallback) - timedelta(days=1)
    return base.strftime("%Y%m%d")


def _chunks(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-codes", nargs="+", default=["005930"])
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--base-dt", default=None, help="YYYYMMDD. Defaults to today KST.")
    parser.add_argument("--minute-scope", default="1", help="ka10080 tic_scope; 1 means 1-minute bars.")
    parser.add_argument("--max-requests-per-stock", type=int, default=4)
    parser.add_argument("--max-rows-per-stock", type=int, default=3000)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--page-delay", type=float, default=0.15, help="Delay between ka10080 continuation pages for one stock.")
    parser.add_argument("--trading-env", choices=["mock", "prod"], default=None, help="Kiwoom env for historical data collection. Defaults to BACKTEST_KIWOOM_ENV or mock.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    start_base = args.base_dt or now_kst.strftime("%Y%m%d")
    cutoff = now_kst - timedelta(days=args.days)
    blocks: list[str] = []
    alerts: list[str] = []
    per_stock: dict[str, Any] = {}
    payload: list[dict[str, Any]] = []
    mode = resolve_execution_mode(purpose="collect_intraday_90d", requested_env=args.trading_env, env=load_env(PROJECT_ROOT / ".env"))
    if not mode.can_collect_history:
        blocks.append("historical_collection_mode_not_allowed")

    codes: list[str] = []
    for raw_code in args.stock_codes:
        code = normalize_stock_code(raw_code)
        if code and code not in codes:
            codes.append(code)
    if not codes:
        blocks.append("no_stock_codes_requested")

    sb: SupabaseRestClient | None = None
    if not args.dry_run:
        try:
            sb = SupabaseRestClient()
        except SupabaseRestError as exc:
            blocks.append(str(exc))

    if not blocks:
        client = KiwoomAPIClient.from_env(PROJECT_ROOT / ".env", trading_env=mode.kiwoom_env)
        market = MarketDataService(client)
        for code_idx, code in enumerate(codes):
            if code_idx and args.delay > 0:
                time.sleep(args.delay)
            base_dt = start_base
            seen_ts: set[str] = set()
            stock_payload: list[dict[str, Any]] = []
            stock_alerts: list[str] = []
            request_summaries: list[dict[str, Any]] = []
            oldest_ts: datetime | None = None
            newest_ts: datetime | None = None
            cont_yn = "N"
            next_key = ""
            for request_no in range(1, args.max_requests_per_stock + 1):
                if request_no > 1 and args.page_delay > 0:
                    time.sleep(args.page_delay)
                try:
                    page = market.get_minute_chart_page(
                        code,
                        base_dt=base_dt,
                        minute_scope=args.minute_scope,
                        cont_yn=cont_yn,
                        next_key=next_key,
                    )
                    rows = page["rows"]
                except Exception as exc:  # noqa: BLE001
                    stock_alerts.append(f"ka10080_fetch_failed:{type(exc).__name__}")
                    break
                converted = 0
                skipped = 0
                request_oldest: datetime | None = None
                request_newest: datetime | None = None
                for raw in rows:
                    row, err, ts = _row_to_payload(code, raw)
                    if ts is not None:
                        request_oldest = ts if request_oldest is None or ts < request_oldest else request_oldest
                        request_newest = ts if request_newest is None or ts > request_newest else request_newest
                    if err:
                        skipped += 1
                        continue
                    assert row is not None
                    if row["timestamp"] in seen_ts:
                        continue
                    seen_ts.add(row["timestamp"])
                    row_ts = _parse_cntr_tm(raw)
                    if row_ts is not None and row_ts < cutoff:
                        continue
                    stock_payload.append(row)
                    converted += 1
                    if row_ts is not None:
                        oldest_ts = row_ts if oldest_ts is None or row_ts < oldest_ts else oldest_ts
                        newest_ts = row_ts if newest_ts is None or row_ts > newest_ts else newest_ts
                    if len(stock_payload) >= args.max_rows_per_stock:
                        break
                request_summaries.append(
                    {
                        "request_no": request_no,
                        "base_dt": base_dt,
                        "raw_rows": len(rows),
                        "converted_new_rows": converted,
                        "skipped_rows": skipped,
                        "oldest_cntr_tm": request_oldest.isoformat() if request_oldest else None,
                        "newest_cntr_tm": request_newest.isoformat() if request_newest else None,
                        "cont_yn": page.get("cont_yn"),
                        "next_key_present": bool(page.get("next_key")),
                    }
                )
                if not rows:
                    stock_alerts.append("ka10080_empty_response")
                    break
                if len(stock_payload) >= args.max_rows_per_stock:
                    break
                if oldest_ts is not None and oldest_ts <= cutoff:
                    break
                if page.get("cont_yn") == "Y" and page.get("next_key"):
                    cont_yn = "Y"
                    next_key = str(page["next_key"])
                else:
                    cont_yn = "N"
                    next_key = ""
                    base_dt = _next_base_dt(request_oldest or oldest_ts, now_kst)
            if not stock_payload:
                stock_alerts.append("no_valid_ka10080_rows")
            payload.extend(stock_payload)
            per_stock[code] = {
                "rows_prepared": len(stock_payload),
                "first_timestamp": oldest_ts.isoformat() if oldest_ts else None,
                "last_timestamp": newest_ts.isoformat() if newest_ts else None,
                "alerts": stock_alerts,
                "requests": request_summaries,
            }
            alerts.extend(f"{code}:{a}" for a in stock_alerts)

    upserted = 0
    if not blocks and not args.dry_run:
        assert sb is not None
        try:
            for batch in _chunks(payload, max(1, args.batch_size)):
                upserted += len(sb.upsert_rows("intraday_prices", batch, on_conflict="stock_code,timestamp,time_frame", timeout=60))
        except SupabaseRestError as exc:
            blocks.append(f"intraday_upsert_failed:{exc}")

    if not payload and not blocks:
        blocks.append("no_ka10080_minute_rows_prepared")

    out = {
        "ok": not blocks,
        "workflow": WORKFLOW,
        "stage": STAGE,
        "status": "completed" if not blocks else "blocked",
        "summary": {
            "source": SOURCE,
            "time_frame": TIME_FRAME,
            "minute_scope": args.minute_scope,
            "execution_mode": redacted_mode_dict(mode),
            "stock_codes": codes,
            "window_days": args.days,
            "base_dt_start": start_base,
            "prepared_rows": len(payload),
            "upserted_rows": upserted,
            "dry_run": args.dry_run,
            "max_requests_per_stock": args.max_requests_per_stock,
            "max_rows_per_stock": args.max_rows_per_stock,
        },
        "per_stock": per_stock,
        "blocking_conditions": blocks,
        "alerts": alerts,
        "next_actions": [
            "수집 후 backtest_opening_strategy.py를 --source kiwoom_ka10080_minute --time-frame 1min으로 실행하세요",
            "cont-yn/next-key 기반 연속조회가 필요하면 KiwoomAPIClient에 continuation 지원을 추가하세요",
            "paper/real 주문은 백테스트 rows/trades/리스크 기준 통과 전까지 계속 금지하세요",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
