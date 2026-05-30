"""Simulate approved orders (paper orders only) for Leader AI workflow.

Reads opening candidate loop + risk checks and writes simulated orders to Supabase
orders table with status=SIMULATED. Never calls Kiwoom order API.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import SupabaseRestClient, SupabaseRestError, num  # noqa: E402
from core.trading_mode import load_env, redacted_mode_dict, resolve_execution_mode  # noqa: E402


def run_json(cmd: list[str], timeout: int = 240) -> tuple[dict[str, Any] | None, str | None, int]:
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, (proc.stderr or proc.stdout)[-1200:], proc.returncode
    return data, proc.stderr[-1200:] if proc.stderr else None, proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", type=int, choices=[10, 30], default=30)
    parser.add_argument("--max-orders", type=int, default=3)
    parser.add_argument("--total-budget", type=float, default=1_000_000)
    parser.add_argument("--per-stock-budget", type=float, default=300_000)
    parser.add_argument("--trading-env", choices=["mock", "prod"], default=None)
    args = parser.parse_args()

    blocks: list[str] = []
    alerts: list[str] = []
    mode = resolve_execution_mode(purpose="simulate_approved_orders", requested_env=args.trading_env, env=load_env(PROJECT_ROOT / ".env"))
    if not mode.can_write_simulated_orders or mode.can_call_real_order_api:
        blocks.append("paper_order_mode_guard_failed")

    loop, err, rc = run_json([sys.executable, "scripts/run_opening_strategy_candidate_loop.py", "--window", str(args.window), "--limit", "10"], timeout=300)
    if loop is None:
        out = {
            "ok": False,
            "workflow": "leader_approval_order_workflow_v1",
            "stage": "simulate_approved_orders",
            "status": "blocked",
            "blocking_conditions": ["opening_candidate_loop_invalid_json"],
            "error_tail": err,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    blocks.extend(str(x) for x in loop.get("blocking_conditions", []))
    candidates = loop.get("buy_candidates", []) if isinstance(loop.get("buy_candidates"), list) else []
    if not candidates:
        blocks.append("no_buy_candidates_for_simulation")

    risk, risk_err, _ = run_json([sys.executable, "scripts/run_daily_workflow_stage.py", "--stage", "premarket_account_risk_check"], timeout=180)
    if risk is None:
        alerts.append("premarket_account_risk_check_unavailable")
    else:
        if risk.get("ok") is False:
            alerts.append("premarket_account_risk_check_not_ok")

    approved = []
    remaining_budget = args.total_budget
    for c in candidates:
        if len(approved) >= args.max_orders:
            break
        if c.get("blocking_conditions"):
            continue
        code = str(c.get("stock_code") or "")
        price = num(c.get("current_price") or c.get("candidate", {}).get("price") or c.get("entry_price") or 0)
        score = num(c.get("score") or 0)
        if not code or price <= 0:
            continue
        if score < 70:
            continue
        budget = min(args.per_stock_budget, remaining_budget)
        qty = int(budget // price)
        if qty <= 0:
            continue
        order_value = qty * price
        remaining_budget -= order_value
        approved.append(
            {
                "order_id": f"SIM-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{code}",
                "stock_code": code,
                "order_type": "BUY",
                "quantity": qty,
                "price": price,
                "status": "SIMULATED",
                "strategy": "opening_multi_factor_v1",
                "raw_response": {
                    "source": "leader_approval_order_workflow_v1",
                    "mode": "paper",
                    "window": args.window,
                    "score": score,
                },
            }
        )
        if remaining_budget <= 0:
            break

    if not approved and not blocks:
        blocks.append("no_orders_passed_budget_or_score")

    inserted = []
    if approved:
        try:
            sb = SupabaseRestClient()
            inserted = sb.insert_rows("orders", approved)
        except SupabaseRestError as exc:
            blocks.append(f"simulated_order_insert_failed:{exc}")

    out = {
        "ok": not blocks,
        "workflow": "leader_approval_order_workflow_v1",
        "stage": "simulate_approved_orders",
        "status": "completed" if not blocks else "blocked",
        "summary": {
            "window": args.window,
            "candidate_buy_count": len(candidates),
            "approved_order_count": len(approved),
            "inserted_order_count": len(inserted),
            "remaining_budget": round(remaining_budget, 2),
            "mode": "paper_only",
            "execution_mode": redacted_mode_dict(mode),
        },
        "approved_orders": approved,
        "inserted_orders": inserted,
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts,
        "next_actions": [
            "SIMULATED 주문만 생성됩니다. Kiwoom 실주문 API는 호출하지 않습니다.",
            "Leader 승인 플로우와 Telegram 승인 단계를 통과한 케이스만 모의 주문으로 반영하세요.",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
