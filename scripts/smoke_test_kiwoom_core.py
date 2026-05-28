#!/usr/bin/env python3
"""Smoke test for the stable core Kiwoom modules.

No secrets are printed. This script intentionally calls only read-only APIs.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.account_service import AccountService
from core.kiwoom_client import KiwoomAPIClient, money
from core.market_data_service import MarketDataService


def main() -> int:
    client = KiwoomAPIClient.from_env(ROOT / ".env", trading_env="mock")
    account = AccountService(client)
    market = MarketDataService(client)

    print("Stable Kiwoom core smoke test")
    print(f"env_file={ROOT / '.env'}")
    print(f"trading_env={client.config.trading_env}")
    print(f"base_url={client.config.base_url}")
    print(f"api_key_present={bool(client.config.api_key)}")
    print(f"api_secret_present={bool(client.config.api_secret)}")
    print(f"account_no_present={bool(client.config.account_no)}")

    client.issue_token()
    print("\n[0] OAuth token: OK (hidden)")

    stock_info = market.get_stock_info("005930")
    stock_summary = {
        "ok": stock_info.get("return_code") == 0,
        "return_code": stock_info.get("return_code"),
        "return_msg": stock_info.get("return_msg"),
        "stk_cd": stock_info.get("stk_cd"),
        "stk_nm": stock_info.get("stk_nm"),
        "cur_prc": stock_info.get("cur_prc"),
        "per": stock_info.get("per"),
        "pbr": stock_info.get("pbr"),
    }

    account_summary = account.get_account_summary()
    account_payload = {
        "ok": account_summary.raw_return_msg in ("모의투자 조회완료", "정상적으로 처리되었습니다"),
        "return_msg": account_summary.raw_return_msg,
        "deposit": money(account_summary.deposit),
        "estimated_asset": money(account_summary.estimated_asset),
        "holdings_count": account_summary.holdings_count,
        "holdings": [
            {
                "code": h.code,
                "name": h.name,
                "quantity": h.quantity,
                "avg_price": money(h.avg_price),
                "current_price": money(h.current_price),
                "evaluation": money(h.evaluation),
                "pnl_amount": money(h.pnl_amount),
                "pnl_pct": h.pnl_pct,
            }
            for h in account_summary.holdings[:5]
        ],
    }

    daily_prices = market.get_daily_prices("005930", base_dt=date.today().strftime("%Y%m%d"))
    latest = daily_prices[0] if daily_prices else None
    chart_payload = {
        "ok": bool(daily_prices),
        "rows": len(daily_prices),
        "latest_date": latest.date if latest else None,
        "latest_close": money(latest.close if latest else None),
    }

    rankings = market.get_kospi_volume_ranking(limit=100)
    ranking_payload = {
        "ok": bool(rankings),
        "rows": len(rankings),
        "first_items": [
            {
                "stock_code": item.stock_code,
                "stock_name": item.stock_name,
                "current_price": money(item.current_price),
                "trading_volume": item.trading_volume,
            }
            for item in rankings[:3]
        ],
    }

    daily_probe = account.probe_daily_balance_pnl()
    daily_probe_payload = {
        "ok": daily_probe.get("ok"),
        "unsupported_in_mock": daily_probe.get("unsupported_in_mock"),
        "selected_date": daily_probe.get("selected_date"),
        "attempts": daily_probe.get("attempts"),
    }

    outputs = {
        "ka10001_stock_info": stock_summary,
        "kt00004_account_summary": account_payload,
        "ka10081_daily_chart": chart_payload,
        "ka10030_kospi_volume_ranking": ranking_payload,
        "optional_ka01690_probe": daily_probe_payload,
    }
    print("\n=== module results ===")
    print(json.dumps(outputs, ensure_ascii=False, indent=2))

    required_ok = all([
        stock_summary["ok"],
        account_payload["ok"],
        chart_payload["ok"],
        ranking_payload["ok"],
    ])
    print(f"\nRESULT={'OK' if required_ok else 'CHECK_NEEDED'}")
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
