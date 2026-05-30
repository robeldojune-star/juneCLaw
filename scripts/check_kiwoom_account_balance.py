"""Read-only Kiwoom account balance/evaluation check.

No order API is called. Account number and secrets are never printed.
Use this to discover paper/mock or real account buying power before paper/real gates.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.kiwoom_client import KiwoomAPIClient, KiwoomAPIError, clean_int  # noqa: E402
from core.trading_mode import load_env, normalize_trading_env  # noqa: E402


def pick_amount(data: dict[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        if key in data:
            value = clean_int(data.get(key), abs_value=True)
            if value is not None:
                return value
    nested = data.get("data")
    if isinstance(nested, dict):
        for key in keys:
            if key in nested:
                value = clean_int(nested.get(key), abs_value=True)
                if value is not None:
                    return value
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trading-env", choices=["mock", "prod"], default=None)
    args = parser.parse_args()

    env = load_env(PROJECT_ROOT / ".env")
    trading_env = normalize_trading_env(args.trading_env or env.get("TRADING_ENV") or "mock")
    blocks: list[str] = []
    alerts: list[str] = []

    try:
        client = KiwoomAPIClient.from_env(PROJECT_ROOT / ".env", trading_env=trading_env)
        account_no = client.config.account_no
        if not account_no:
            blocks.append("kiwoom_account_no_missing")
            raise SystemExit
        response = client.post(
            "kt00004",
            "/api/dostk/acnt",
            {"accno": account_no, "qry_tp": "1", "dmst_stex_tp": "KRX"},
            raise_on_error=True,
        )
        data = response.data
        holdings = data.get("stk_acnt_evlt_prst") or data.get("holdings") or data.get("data", {}).get("holdings") or []
        cash = pick_amount(data, ["entr", "deposit", "ord_psbl_cash", "dnca_tot_amt", "cash_balance"])
        total_estimated = pick_amount(data, ["tot_est_amt", "estimated_asset", "tot_evlt_amt", "tot_asst_amt"])
        out = {
            "ok": True,
            "stage": "check_kiwoom_account_balance",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "summary": {
                "trading_env": trading_env,
                "account_no_present": bool(account_no),
                "account_no_redacted": "[REDACTED]",
                "cash_or_deposit": cash,
                "total_estimated_asset": total_estimated,
                "holdings_count": len(holdings) if isinstance(holdings, list) else None,
                "read_only": True,
            },
            "blocking_conditions": [],
            "alerts": alerts,
            "next_actions": [
                "금액은 주문 가능 예산 산정용으로만 사용하고, 계좌번호/토큰은 출력하지 않습니다.",
                "실전 주문은 별도 real-order multi-key gate와 사용자 승인 없이는 호출하지 않습니다.",
            ],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except SystemExit:
        pass
    except KiwoomAPIError as exc:
        blocks.append(f"kiwoom_account_query_failed:{exc.api_id or 'unknown'}:{exc.return_code}")
    except Exception as exc:  # noqa: BLE001
        blocks.append(f"kiwoom_account_query_failed:{type(exc).__name__}")

    out = {
        "ok": False,
        "stage": "check_kiwoom_account_balance",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "trading_env": trading_env,
            "account_no_redacted": "[REDACTED]",
            "read_only": True,
        },
        "blocking_conditions": blocks,
        "alerts": alerts,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
