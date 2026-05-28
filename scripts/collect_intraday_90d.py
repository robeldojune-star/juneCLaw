"""Collect real intraday bars (ka10005 candidate) into Supabase intraday_prices.

Real-data-first: if API/data are unavailable, return blocking_conditions.
No synthetic rows are created.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.kiwoom_client import KiwoomAPIClient, clean_int  # noqa: E402
from core.market_data_service import MarketDataService  # noqa: E402
from core.supabase_rest import SupabaseRestClient, SupabaseRestError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-codes", nargs="+", default=["005930"])
    parser.add_argument("--time-frame", default="1min")
    parser.add_argument("--max-per-stock", type=int, default=300)
    args = parser.parse_args()

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    cutoff = now_kst - timedelta(days=130)

    blocks: list[str] = []
    alerts: list[str] = []
    inserted = 0
    attempted = 0

    try:
        sb = SupabaseRestClient()
    except SupabaseRestError as exc:
        out = {
            "ok": False,
            "workflow": "daily_trading_workflow_v1",
            "stage": "collect_intraday_90d",
            "status": "blocked",
            "blocking_conditions": [str(exc)],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    client = KiwoomAPIClient.from_env(PROJECT_ROOT / ".env")
    market = MarketDataService(client)

    for code in args.stock_codes:
        try:
            rows = market.get_intraday_ohlcv_raw(code)[: args.max_per_stock]
        except Exception as exc:  # noqa: BLE001
            alerts.append(f"{code}_intraday_fetch_failed:{type(exc).__name__}")
            continue
        payload = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            ds = str(r.get("date") or "").strip()
            if len(ds) < 8:
                continue
            day = ds[:8]
            # ka10005 does not always expose explicit HHMMSS; assume market-close bucket when missing.
            tm = "153000"
            timestamp = f"{day[:4]}-{day[4:6]}-{day[6:8]}T{tm[:2]}:{tm[2:4]}:{tm[4:6]}+09:00"
            # keep only ~90 trading days equivalent window
            try:
                dt = datetime.fromisoformat(timestamp.replace("+09:00", "+09:00"))
            except Exception:
                continue
            if dt.astimezone(ZoneInfo("Asia/Seoul")) < cutoff:
                continue
            payload.append(
                {
                    "stock_code": code,
                    "timestamp": timestamp,
                    "time_frame": args.time_frame,
                    "open": clean_int(r.get("open_pric"), abs_value=True),
                    "high": clean_int(r.get("high_pric"), abs_value=True),
                    "low": clean_int(r.get("low_pric"), abs_value=True),
                    "close": clean_int(r.get("close_pric"), abs_value=True),
                    "volume": clean_int(r.get("trde_qty"), abs_value=True),
                    "trading_value": clean_int(r.get("trde_prica"), abs_value=True),
                    "source": "kiwoom_ka10005",
                }
            )
        attempted += len(payload)
        if not payload:
            alerts.append(f"{code}_no_payload_rows")
            continue
        try:
            up = sb.upsert_rows("intraday_prices", payload, on_conflict="stock_code,timestamp,time_frame")
            inserted += len(up)
        except SupabaseRestError as exc:
            alerts.append(f"{code}_intraday_upsert_failed:{exc}")

    if attempted == 0:
        blocks.append("no_intraday_rows_attempted")

    out = {
        "ok": not blocks,
        "workflow": "daily_trading_workflow_v1",
        "stage": "collect_intraday_90d",
        "status": "completed" if not blocks else "blocked",
        "summary": {
            "stock_codes": args.stock_codes,
            "attempted_rows": attempted,
            "upserted_rows": inserted,
            "time_frame": args.time_frame,
            "window_days": 130,
        },
        "blocking_conditions": blocks,
        "alerts": alerts,
        "next_actions": [
            "upserted_rows가 충분하지 않으면 장중 반복 수집 스케줄을 추가하세요",
            "ka10005 시간축 검증 통과 전 백테스트 결과를 주문 근거로 사용하지 마세요",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
