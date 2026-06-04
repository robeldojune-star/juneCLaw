"""Run a named daily trading workflow stage and emit standard JSON for n8n.

Design goals:
- one command shape for every n8n Execute Command node
- no fake market data
- no order execution from this runner
- explicit blocking_conditions when dependencies/data are missing
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.workflow_result import WorkflowStep, make_result, utc_now_iso  # noqa: E402

WORKFLOW = "daily_trading_workflow_v1"

STAGE_META: dict[str, dict[str, str]] = {
    "system_health_check": {"model_grade": "none", "time": "06:50"},
    "news_briefing_growth_analysis": {"model_grade": "medium_high", "time": "07:00"},
    "stock_morning_signals": {"model_grade": "medium", "time": "07:30"},
    "stock_trading_daily_workflow": {"model_grade": "low_medium", "time": "08:00"},
    "premarket_account_risk_check": {"model_grade": "low", "time": "08:30"},
    "candidate_compression_layer": {"model_grade": "medium", "time": "08:45"},
    "today_watchlist": {"model_grade": "low", "time": "08:50"},
    "morning_investment_layer": {"model_grade": "low", "time": "09:00"},
    "collect_current_session_snapshots": {"model_grade": "none", "time": "09:05~15:30"},
    "intraday_timing_alert_10m": {"model_grade": "low", "time": "09:10~15:30"},
    "intraday_timing_alert_30m": {"model_grade": "low", "time": "09:30~15:30"},
    "opening_10m_aggressive_layer": {"model_grade": "low", "time": "09:10"},
    "opening_30m_standard_layer": {"model_grade": "low", "time": "09:30"},
    "post_opening_monitoring": {"model_grade": "low", "time": "10:00"},
    "midday_position_review": {"model_grade": "low", "time": "11:30"},
    "pre_close_risk_review": {"model_grade": "low", "time": "14:30"},
    "evening_selloff_layer": {"model_grade": "low", "time": "15:00"},
    "aftermarket_multi_timeframe_collection": {"model_grade": "none", "time": "15:20"},
    "stock_nightly_collection": {"model_grade": "none", "time": "15:40"},
    "daily_pnl_feedback_report": {"model_grade": "medium", "time": "16:10"},
    "ka10005_timeframe_validation": {"model_grade": "none", "time": "09:20"},
    "collect_intraday_90d": {"model_grade": "none", "time": "15:50"},
    "backtest_opening_strategy_90d": {"model_grade": "medium", "time": "20:30"},
    "simulate_approved_orders": {"model_grade": "low", "time": "09:35"},
    "strategy_review_if_needed": {"model_grade": "high", "time": "20:00"},
}


def _read_env_keys() -> dict[str, str]:
    env_path = PROJECT_ROOT / ".env"
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for raw in env_path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        # Strip inline comments without exposing secret values.
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        out[key.strip()] = value
    return out


def _run_command(name: str, args: list[str], timeout: int = 180) -> WorkflowStep:
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
        return WorkflowStep(name=name, ok=False, status="error", error=f"{type(exc).__name__}: {exc}", blocking_conditions=[f"{name}_failed"])

    parsed: Any = None
    stdout = proc.stdout.strip()
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = {"stdout_tail": stdout[-1200:]}
    ok = proc.returncode == 0
    blocks: list[str] = []
    if isinstance(parsed, dict):
        blocks.extend(str(x) for x in parsed.get("blocking_conditions", []) if x)
        if parsed.get("ok") is False and not blocks:
            blocks.append(f"{name}_blocked")
    if not ok and not blocks:
        blocks.append(f"{name}_failed")
    return WorkflowStep(
        name=name,
        ok=ok,
        status="completed" if ok else "blocked",
        summary="command executed" if ok else "command failed or blocked",
        details={"returncode": proc.returncode, "parsed": parsed, "stderr_tail": proc.stderr.strip()[-1200:]},
        blocking_conditions=blocks,
        error=None if ok else proc.stderr.strip()[-1200:] or stdout[-1200:],
    )


def stage_system_health_check() -> list[WorkflowStep]:
    env = _read_env_keys()
    # Support environment-suffixed API keys like _MOCK or _PROD
    trading_env = (env.get("TRADING_ENV") or "mock").strip().lower()
    suffix = "_PROD" if trading_env == "prod" else "_MOCK"
    
    required = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "DATABASE_URL"]
    present = {k: bool(env.get(k)) for k in required}
    
    # Check Kiwoom Keys with support for fallback / environment-suffixed variants
    kiwoom_keys = ["KIWOOM_REST_API_KEY", "KIWOOM_REST_API_SECRET"]
    for k in kiwoom_keys:
        has_key = bool(env.get(f"{k}{suffix}")) or bool(env.get(k))
        present[k] = has_key
        
    blocks = [f"missing_env_{k}" for k, ok in present.items() if not ok]
    steps = [WorkflowStep(name="env_presence", ok=not blocks, summary="required env keys presence checked; values hidden", details={"present": present}, blocking_conditions=blocks)]
    steps.append(_run_command("kiwoom_core_smoke", [sys.executable, "scripts/smoke_test_kiwoom_core.py"], timeout=120))
    return steps


def stage_news_briefing_growth_analysis() -> list[WorkflowStep]:
    return [_run_command("news_briefing_growth_analysis", [sys.executable, "scripts/news_briefing_growth_analysis.py"], timeout=120)]


def stage_stock_morning_signals() -> list[WorkflowStep]:
    # trading-runner Docker image already contains psycopg; host environments may
    # have uv, but Docker runner does not. Prefer the current Python executable
    # so n8n/Hermes runner behavior is stable.
    return [_run_command("generate_daily_signals", [sys.executable, "scripts/generate_daily_signals.py"], timeout=300)]


def stage_stock_trading_daily_workflow() -> list[WorkflowStep]:
    return [
        _run_command("collect_kospi_top50", [sys.executable, "scripts/collect_kospi_top50.py"], timeout=240),
        _run_command("calculate_technical_indicators", [sys.executable, "scripts/calculate_technical_indicators.py"], timeout=240),
        _run_command("generate_daily_signals", [sys.executable, "scripts/generate_daily_signals.py"], timeout=240),
    ]


def stage_premarket_account_risk_check() -> list[WorkflowStep]:
    return [
        _run_command("kiwoom_mock_account_balance_check", [sys.executable, "scripts/check_kiwoom_account_balance.py", "--trading-env", "mock"], timeout=120),
        _run_command("kiwoom_prod_account_balance_check_read_only", [sys.executable, "scripts/check_kiwoom_account_balance.py", "--trading-env", "prod"], timeout=120),
    ]


def stage_candidate_compression_layer() -> list[WorkflowStep]:
    return [_run_command("candidate_compression_layer", [sys.executable, "scripts/candidate_compression_layer.py"], timeout=120)]


def stage_today_watchlist() -> list[WorkflowStep]:
    return [_run_command("today_watchlist", [sys.executable, "scripts/build_today_watchlist.py"], timeout=180)]


def stage_morning_investment_layer() -> list[WorkflowStep]:
    return [
        WorkflowStep(
            name="market_open_guard",
            ok=True,
            summary="09:00 layer is observation-only; immediate buy is disabled by design",
            details={"order_execution_enabled": False, "guard_minutes": "09:00~09:05"},
        )
    ]


def stage_collect_current_session_snapshots() -> list[WorkflowStep]:
    return [_run_command("collect_current_session_snapshots", [sys.executable, "scripts/collect_current_session_snapshots.py", "--limit", "20", "--trading-env", "prod"], timeout=240)]


def stage_intraday_timing_alert(window: int) -> list[WorkflowStep]:
    return [
        _run_command(
            f"intraday_timing_alert_{window}m",
            [sys.executable, "scripts/run_intraday_timing_alerts.py", "--window", str(window), "--limit", "10"],
            timeout=240,
        )
    ]


def stage_opening_layer(window: int, stage_name: str) -> list[WorkflowStep]:
    mode_block = "pattern_model_not_ready_for_auto_order"
    steps = [
        _run_command("collect_current_session_snapshots", [sys.executable, "scripts/collect_current_session_snapshots.py", "--limit", "20", "--trading-env", "prod"], timeout=240),
        _run_command(
            stage_name,
            [sys.executable, "scripts/run_opening_strategy_candidate_loop.py", "--window", str(window), "--limit", "10"],
            timeout=300,
        )
    ]
    steps.append(
        WorkflowStep(
            name=f"auto_order_guard_{window}m",
            ok=True,
            status="blocked",
            summary="opening strategy evaluates compressed TOP candidates only; auto order disabled until ka10080 backtest + paper validation passes",
            blocking_conditions=[mode_block, "ka10080_backtest_and_paper_validation_required"],
            details={"window_minutes": window, "order_execution_enabled": False, "candidate_source": "candidate_compression_layer", "bar_source": "kiwoom_ka10006_snapshot", "backtest_source": "kiwoom_ka10080_minute"},
        )
    )
    return steps


def stage_monitoring(stage: str) -> list[WorkflowStep]:
    return [_run_command(stage, [sys.executable, "scripts/position_monitoring_stage.py", "--stage", stage], timeout=120)]


def stage_aftermarket_collection() -> list[WorkflowStep]:
    return [_run_command("collect_daily_prices_kiwoom", [sys.executable, "scripts/collect_daily_prices_kiwoom.py"], timeout=300)]


def stage_stock_nightly_collection() -> list[WorkflowStep]:
    return [
        _run_command("validate_samsung_chart", [sys.executable, "scripts/validate_samsung_chart.py"], timeout=300),
        _run_command("calculate_technical_indicators", [sys.executable, "scripts/calculate_technical_indicators.py"], timeout=240),
    ]


def stage_daily_pnl_feedback_report() -> list[WorkflowStep]:
    return [_run_command("daily_pnl_feedback_report", [sys.executable, "scripts/daily_pnl_feedback_report.py"], timeout=180)]


def stage_ka10005_timeframe_validation() -> list[WorkflowStep]:
    return [_run_command("ka10005_timeframe_validation", [sys.executable, "scripts/validate_ka10005_timeframe.py"], timeout=180)]


def stage_collect_intraday_90d() -> list[WorkflowStep]:
    return [
        _run_command(
            "collect_intraday_90d",
            [
                sys.executable,
                "scripts/collect_intraday_90d.py",
                "--stock-codes",
                "005930",
                "000660",
                "035420",
                "005380",
                "068270",
                "--days",
                "90",
                "--max-requests-per-stock",
                "4",
                "--max-rows-per-stock",
                "3000",
                "--trading-env",
                "prod",
            ],
            timeout=600,
        )
    ]


def stage_backtest_opening_strategy_90d() -> list[WorkflowStep]:
    return [_run_command("backtest_opening_strategy_90d", [sys.executable, "scripts/backtest_opening_strategy.py", "--stock-codes", "005930", "000660", "035420", "005380", "068270", "--days", "130", "--time-frame", "1min", "--source", "kiwoom_ka10080_minute", "--eligible-opening-only", "--fee-bps", "23", "--slippage-bps", "10"], timeout=300)]


def stage_simulate_approved_orders() -> list[WorkflowStep]:
    return [_run_command("simulate_approved_orders", [sys.executable, "scripts/simulate_approved_orders.py", "--window", "30", "--max-orders", "3", "--total-budget", "1000000", "--per-stock-budget", "300000"], timeout=300)]


STAGE_HANDLERS = {
    "system_health_check": stage_system_health_check,
    "news_briefing_growth_analysis": stage_news_briefing_growth_analysis,
    "stock_morning_signals": stage_stock_morning_signals,
    "stock_trading_daily_workflow": stage_stock_trading_daily_workflow,
    "premarket_account_risk_check": stage_premarket_account_risk_check,
    "candidate_compression_layer": stage_candidate_compression_layer,
    "today_watchlist": stage_today_watchlist,
    "morning_investment_layer": stage_morning_investment_layer,
    "collect_current_session_snapshots": stage_collect_current_session_snapshots,
    "intraday_timing_alert_10m": lambda: stage_intraday_timing_alert(10),
    "intraday_timing_alert_30m": lambda: stage_intraday_timing_alert(30),
    "opening_10m_aggressive_layer": lambda: stage_opening_layer(10, "opening_10m_aggressive_layer"),
    "opening_30m_standard_layer": lambda: stage_opening_layer(30, "opening_30m_standard_layer"),
    "post_opening_monitoring": lambda: stage_monitoring("post_opening_monitoring"),
    "midday_position_review": lambda: stage_monitoring("midday_position_review"),
    "pre_close_risk_review": lambda: stage_monitoring("pre_close_risk_review"),
    "evening_selloff_layer": lambda: [_run_command("evening_selloff_layer", [sys.executable, "scripts/evening_selloff_layer.py"], timeout=120)],
    "aftermarket_multi_timeframe_collection": stage_aftermarket_collection,
    "stock_nightly_collection": stage_stock_nightly_collection,
    "daily_pnl_feedback_report": stage_daily_pnl_feedback_report,
    "ka10005_timeframe_validation": stage_ka10005_timeframe_validation,
    "collect_intraday_90d": stage_collect_intraday_90d,
    "backtest_opening_strategy_90d": stage_backtest_opening_strategy_90d,
    "simulate_approved_orders": stage_simulate_approved_orders,
    "strategy_review_if_needed": lambda: [WorkflowStep(name="strategy_review_manual_gate", ok=True, status="blocked", summary="run only when daily/weekly feedback requires strategy changes", blocking_conditions=["manual_strategy_review_gate"])],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=sorted(STAGE_HANDLERS))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    started = utc_now_iso()
    meta = STAGE_META.get(args.stage, {})
    steps = STAGE_HANDLERS[args.stage]()
    result = make_result(
        workflow=WORKFLOW,
        stage=args.stage,
        started_at=started,
        model_grade=meta.get("model_grade", "none"),
        steps=steps,
        summary={"scheduled_time": meta.get("time"), "workspace": str(PROJECT_ROOT)},
        next_actions=["Review blocking_conditions before enabling downstream order workflows"],
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
