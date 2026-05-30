"""Check backtest readiness based on live snapshot_1m quality and stage outputs.

Real-data only. No mutation/write side effects.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KST = ZoneInfo("Asia/Seoul")


def is_market_lag_enforced(now_kst: datetime) -> bool:
    """Only treat latest-lag as a hard blocker during the live session.

    After close, a 15:20~15:30 latest snapshot can be healthy even though
    wall-clock lag grows every minute. Backtest readiness should not fail for
    that after-hours lag.
    """
    if now_kst.weekday() >= 5:
        return False
    return time(9, 0) <= now_kst.time() <= time(15, 40)


def run_json(cmd: list[str], timeout: int = 300) -> tuple[dict[str, Any] | None, str | None, int]:
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    out = (proc.stdout or "").strip()
    try:
        data = json.loads(out) if out else None
    except json.JSONDecodeError:
        return None, (proc.stderr or out)[-1500:], proc.returncode
    return data if isinstance(data, dict) else None, proc.stderr[-1500:] if proc.stderr else None, proc.returncode


def main() -> int:
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat(timespec="seconds")
    now_kst = now_dt.astimezone(KST)
    enforce_lag = is_market_lag_enforced(now_kst)
    blocks: list[str] = []
    alerts: list[str] = []

    snap, snap_err, _ = run_json([
        sys.executable,
        "scripts/inspect_snapshot_1m_status.py",
        "--days",
        "1",
        "--limit",
        "5000",
        "--min-rows",
        "20",
        "--min-codes",
        "5",
        "--max-lag-minutes",
        "15",
    ])

    if snap is None:
        blocks.append("snapshot_status_invalid_json")
        if snap_err:
            alerts.append(snap_err)
        snap_summary = {}
    else:
        snap_summary = dict(snap.get("summary") or {})
        lag = float(snap_summary.get("latest_lag_minutes") or 999)
        quality = dict(snap_summary.get("quality_error_counts") or {})
        duplicates = int(snap_summary.get("duplicate_stock_timestamp_keys") or 0)
        rows = int(snap_summary.get("rows") or 0)
        active_codes = int(snap_summary.get("active_codes") or 0)

        if enforce_lag and lag > 10:
            blocks.append("snapshot_lag_over_10m")
        if quality:
            blocks.append("snapshot_quality_errors_present")
        if duplicates > 0:
            blocks.append("snapshot_duplicate_keys_present")
        if rows < 300:
            blocks.append("snapshot_rows_below_300")
        if active_codes < 10:
            blocks.append("snapshot_active_codes_below_10")

    backtest, back_err, _ = run_json([
        sys.executable,
        "scripts/run_daily_workflow_stage.py",
        "--stage",
        "backtest_opening_strategy_90d",
    ], timeout=420)

    bt_summary: dict[str, Any] = {}
    bt_blocks: list[str] = []
    bt_variants: dict[str, Any] = {}
    if backtest is None:
        blocks.append("backtest_stage_invalid_json")
        if back_err:
            alerts.append(back_err)
    else:
        # stage wrapper -> steps[0].details.parsed.summary
        steps = backtest.get("steps") if isinstance(backtest.get("steps"), list) else []
        parsed = None
        if steps and isinstance(steps[0], dict):
            details = steps[0].get("details") if isinstance(steps[0].get("details"), dict) else {}
            parsed = details.get("parsed") if isinstance(details.get("parsed"), dict) else None
        if isinstance(parsed, dict):
            bt_summary = dict(parsed.get("summary") or {})
            bt_variants = dict(parsed.get("variants") or {})
            bt_blocks = [str(x) for x in parsed.get("blocking_conditions", []) if x]
        else:
            bt_summary = dict(backtest.get("summary") or {})
            bt_variants = dict(backtest.get("variants") or {})
            bt_blocks = [str(x) for x in backtest.get("blocking_conditions", []) if x]

        rows_used = int(bt_summary.get("rows_used") or 0)
        min_rows_required = int(bt_summary.get("min_rows_required") or 300)
        trades = int(bt_summary.get("total_variant_trades") or 0)
        min_trades = int(bt_summary.get("min_trades_required") or 5)

        if rows_used < min_rows_required:
            blocks.append("backtest_rows_below_min_required")
        if trades < min_trades:
            blocks.append("backtest_trades_below_min_required")
        variant_avg_returns: list[float] = []
        for v in bt_variants.values():
            if not isinstance(v, dict):
                continue
            avg_return = v.get("avg_return_pct")
            if avg_return is None:
                continue
            try:
                variant_avg_returns.append(float(avg_return))
            except (TypeError, ValueError):
                continue
        if variant_avg_returns and max(variant_avg_returns) <= 0:
            blocks.append("backtest_avg_return_not_positive")

    out = {
        "ok": not blocks,
        "workflow": "daily_trading_workflow_v1",
        "stage": "check_backtest_readiness",
        "generated_at": now,
        "status": "completed" if not blocks else "blocked",
        "summary": {
            "snapshot": snap_summary,
            "backtest": bt_summary,
            "backtest_variants": bt_variants,
            "backtest_stage_blocks": bt_blocks,
            "readiness_gate": {
                "lag_enforced": enforce_lag,
                "snapshot_quality_ok": "snapshot_quality_errors_present" not in blocks and "snapshot_duplicate_keys_present" not in blocks,
                "snapshot_lag_ok": "snapshot_lag_over_10m" not in blocks,
                "snapshot_volume_ok": "snapshot_rows_below_300" not in blocks and "snapshot_active_codes_below_10" not in blocks,
                "backtest_rows_ok": "backtest_rows_below_min_required" not in blocks,
                "backtest_trades_ok": "backtest_trades_below_min_required" not in blocks,
                "backtest_performance_ok": "backtest_avg_return_not_positive" not in blocks,
            },
        },
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": alerts,
        "next_actions": [
            "snapshot_rows_below_300이면 실시간 감시용 ka10006 snapshot_1m 누적을 계속 유지하세요.",
            "backtest_rows_below_min_required이면 ka10080 기반 collect_intraday_90d를 더 긴 기간/종목에 대해 실행하세요.",
            "다음 실제 장중에 lag/rows/active_codes를 재확인하세요. 휴장·주말·장외 latest_timestamp_stale은 고장으로 보지 않습니다.",
            "backtest_trades_below_min_required이면 종목별 rows 편차와 OR 조건 과도 여부를 점검하세요.",
            "backtest_avg_return_not_positive이면 paper 전환 전에 OR 로직/진입·청산 규칙/수수료·슬리피지를 검토하세요.",
            "모든 readiness_gate가 true가 되기 전까지 paper/real order는 계속 금지하세요.",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
