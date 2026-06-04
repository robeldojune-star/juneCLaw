"""Build today's intraday watchlist from candidate_compression_layer output.

This is a bridge between pre-market candidate compression and intraday timing
alerts. It does not send orders and does not modify strategy thresholds.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KST = ZoneInfo("Asia/Seoul")
WORKFLOW = "daily_trading_workflow_v1"
STAGE = "today_watchlist"


def run_candidate_compression() -> tuple[dict[str, Any] | None, str | None, int]:
    proc = subprocess.run(
        [sys.executable, "scripts/candidate_compression_layer.py"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
        check=False,
    )
    stdout = (proc.stdout or "").strip()
    try:
        data = json.loads(stdout) if stdout else None
    except json.JSONDecodeError:
        return None, (proc.stderr or stdout)[-1500:], proc.returncode
    return data if isinstance(data, dict) else None, proc.stderr[-1500:] if proc.stderr else None, proc.returncode


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _morning_reason(candidate: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    strategy = candidate.get("strategy")
    if strategy:
        reasons.append(f"strategy={strategy}")
    reason = candidate.get("reason")
    if reason:
        reasons.append(str(reason))
    signal_score = candidate.get("signal_score")
    if signal_score is not None:
        reasons.append(f"daily_signal_score={signal_score}")
    sector = candidate.get("sector")
    if sector:
        reasons.append(f"sector={sector}")
    return reasons or ["candidate_compression_layer_selected"]


def normalize_candidate(candidate: dict[str, Any], priority: int) -> dict[str, Any]:
    score = _num(candidate.get("compressed_score"), _num(candidate.get("signal_score")))
    base_blocks = [str(x) for x in candidate.get("blocking_conditions", []) if x]
    return {
        "stock_code": str(candidate.get("stock_code") or ""),
        "stock_name": candidate.get("stock_name"),
        "sector": candidate.get("sector"),
        "watch_priority": priority,
        "candidate_score": round(score, 4),
        "signal_type": "BUY" if not base_blocks else "WATCH",
        "strategy": candidate.get("strategy") or "opening_multi_factor_v1",
        "morning_reason": _morning_reason(candidate),
        "score_details": {
            "signal_score": candidate.get("signal_score"),
            "compressed_score": candidate.get("compressed_score"),
            "rank": candidate.get("rank"),
            "price": candidate.get("price"),
        },
        "entry_scenarios": [
            {
                "scenario_id": "or10_breakout",
                "label": "OR10 상단 돌파",
                "time_window": "09:10~10:00",
                "required_conditions": [
                    "current_price > or10_high",
                    "volume_ratio >= 1.5",
                    "snapshot_lag_minutes <= 10",
                ],
                "invalidation_conditions": [
                    "snapshot_1m_quality_error",
                    "gap_up_too_large",
                    "market_wide_risk_on",
                ],
            },
            {
                "scenario_id": "or30_breakout",
                "label": "OR30 상단 돌파/회복",
                "time_window": "09:30~11:00",
                "required_conditions": [
                    "current_price > or30_high",
                    "volume_ratio >= 1.3",
                    "snapshot_lag_minutes <= 10",
                ],
                "invalidation_conditions": [
                    "snapshot_1m_quality_error",
                    "false_breakout_risk_high",
                    "market_wide_risk_on",
                ],
            },
        ],
        "risk_controls": {
            "max_position_krw": 300000,
            "suggested_budget_krw": 0,
            "stop_loss_pct": -0.9,
            "take_profit_pct_1": 1.0,
            "take_profit_pct_2": 2.0,
            "suggested_mode": "alert_only",
            "paper_order_allowed": False,
            "real_order_allowed": False,
        },
        "blocking_conditions": list(dict.fromkeys(base_blocks)),
    }


def main() -> int:
    generated_at = datetime.now(KST).isoformat(timespec="seconds")
    trading_date = datetime.now(KST).date().isoformat()
    comp, err, rc = run_candidate_compression()
    blocks: list[str] = []
    alerts: list[str] = []

    if comp is None:
        out = {
            "ok": False,
            "workflow": WORKFLOW,
            "stage": STAGE,
            "status": "blocked",
            "generated_at": generated_at,
            "trading_date": trading_date,
            "summary": {
                "candidate_count": 0,
                "source_stages": ["candidate_compression_layer"],
                "order_execution_enabled": False,
                "paper_candidate_enabled": False,
            },
            "watchlist": [],
            "blocking_conditions": ["candidate_compression_invalid_json"],
            "alerts": [err] if err else [],
            "next_actions": ["candidate_compression_layer stdout/stderr를 확인하세요."],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    blocks.extend(str(x) for x in comp.get("blocking_conditions", []) if x)
    alerts.extend(str(x) for x in comp.get("alerts", []) if x)
    candidates = comp.get("candidates", []) if isinstance(comp.get("candidates"), list) else []
    watchlist = [normalize_candidate(c, idx + 1) for idx, c in enumerate(candidates[:20])]
    watchlist = [w for w in watchlist if w.get("stock_code")]

    if not watchlist:
        blocks.append("today_watchlist_empty")

    out = {
        "ok": not blocks,
        "workflow": WORKFLOW,
        "stage": STAGE,
        "status": "completed" if not blocks else "blocked",
        "generated_at": generated_at,
        "trading_date": trading_date,
        "summary": {
            "candidate_count": len(watchlist),
            "source_stages": ["news_briefing_growth_analysis", "stock_morning_signals", "candidate_compression_layer"],
            "order_execution_enabled": False,
            "paper_candidate_enabled": False,
            "candidate_compression_status": comp.get("status"),
            "candidate_compression_summary": comp.get("summary"),
        },
        "watchlist": watchlist,
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts,
        "next_actions": [
            "장중에는 이 today_watchlist만 snapshot_1m 기반 OR10/OR30 timing alert 대상으로 평가하세요.",
            "paper/real 주문은 backtest 및 Leader 승인형 workflow 검증 전까지 계속 비활성화하세요.",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
