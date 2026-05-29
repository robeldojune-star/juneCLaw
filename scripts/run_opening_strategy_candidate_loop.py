"""Run opening_multi_factor_v1 for the compressed candidate watchlist.

This bridges candidate_compression_layer -> opening strategy. It never sends orders.
If the candidate list is empty or blocked, it reports blocking_conditions instead
of falling back to fake/sample stocks.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KST = ZoneInfo("Asia/Seoul")


def run_json(args: list[str], timeout: int = 180) -> tuple[dict[str, Any] | None, str | None, int]:
    proc = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, (proc.stderr or proc.stdout)[-1200:], proc.returncode
    return data, proc.stderr[-1200:] if proc.stderr else None, proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", type=int, choices=[10, 30], required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--base-dt", default=None)
    args = parser.parse_args()

    blocks: list[str] = []
    alerts: list[str] = []
    comp, comp_err, comp_rc = run_json([sys.executable, "scripts/candidate_compression_layer.py"], timeout=120)
    if comp is None:
        out = {
            "ok": False,
            "workflow": "daily_trading_workflow_v1",
            "stage": f"opening_{args.window}m_candidate_loop",
            "status": "blocked",
            "blocking_conditions": ["candidate_compression_invalid_json"],
            "error_tail": comp_err,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    blocks.extend(str(x) for x in comp.get("blocking_conditions", []))
    candidates = comp.get("candidates", []) if isinstance(comp.get("candidates"), list) else []
    candidates = candidates[: args.limit]
    if not candidates:
        blocks.append("opening_candidate_list_empty")

    results: list[dict[str, Any]] = []
    for cand in candidates:
        code = str(cand.get("stock_code") or "")
        if not code:
            continue
        cmd = [sys.executable, "scripts/run_opening_strategy_research.py", "--stock-code", code, "--limit-bars", str(args.window)]
        if args.base_dt:
            cmd.extend(["--base-dt", args.base_dt])
        res, err, rc = run_json(cmd, timeout=180)
        if res is None:
            results.append({"stock_code": code, "ok": False, "blocking_conditions": ["opening_strategy_invalid_json"], "error_tail": err})
            continue
        res["candidate"] = cand
        res["ok"] = not bool(res.get("blocking_conditions")) and bool(res.get("ok", True))
        res["status"] = "completed" if res["ok"] else "blocked"
        results.append(res)

    def _fujimoto_gate_passed(item: dict[str, Any]) -> bool:
        raw_details = item.get("score_details")
        details = raw_details if isinstance(raw_details, dict) else {}

        raw_thresholds = details.get("thresholds")
        thresholds = raw_thresholds if isinstance(raw_thresholds, dict) else {}

        raw_fujimoto = details.get("fujimoto_aux_filter")
        fujimoto = raw_fujimoto if isinstance(raw_fujimoto, dict) else {}

        min_required = float(thresholds.get("fujimoto_aux_min", 8))
        aux_score = float(fujimoto.get("score", 0.0))
        return aux_score >= min_required

    buy_candidates = [
        r for r in results
        if r.get("signal_type") == "BUY"
        and not r.get("blocking_conditions")
        and _fujimoto_gate_passed(r)
    ]
    watch_candidates = [r for r in results if r.get("signal_type") in {"BUY", "WATCH", "HOLD"}]
    if not results and candidates:
        blocks.append("opening_strategy_loop_no_results")
    if not buy_candidates:
        alerts.append("no_opening_buy_candidates")

    out = {
        "ok": not blocks,
        "workflow": "daily_trading_workflow_v1",
        "stage": f"opening_{args.window}m_candidate_loop",
        "status": "completed" if not blocks else "blocked",
        "summary": {
            "window_minutes": args.window,
            "candidate_count": len(candidates),
            "evaluated_count": len(results),
            "buy_candidate_count": len(buy_candidates),
            "order_execution_enabled": False,
        },
        "candidate_compression_summary": comp.get("summary"),
        "results": results,
        "buy_candidates": buy_candidates[: args.limit],
        "watch_candidates": watch_candidates[: args.limit],
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts,
        "next_actions": [
            "Leader AI 승인형 주문 workflow가 별도로 승인하기 전 주문 실행 금지",
            "snapshot_1m 누적/백테스트와 Leader 승인형 주문 workflow가 별도로 통과하기 전 주문 실행 금지",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
