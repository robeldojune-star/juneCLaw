"""Trading mode and execution guard helpers.

Purpose:
- Never rely on cron jobs mutating TRADING_ENV.
- Data collection/backtest/paper/real execution declare their intended mode.
- Real order paths require explicit multi-key opt-in.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


def load_env(path: str | Path = ".env") -> dict[str, str]:
    env: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return env
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.split(" #", 1)[0].strip().strip('"').strip("'")
    return env


def normalize_trading_env(value: str | None) -> str:
    return "prod" if str(value or "").strip().lower() == "prod" else "mock"


@dataclass(frozen=True)
class ExecutionMode:
    purpose: str
    kiwoom_env: str
    order_mode: str
    can_collect_history: bool
    can_collect_live_snapshot: bool
    can_write_simulated_orders: bool
    can_call_real_order_api: bool
    reason: str


def resolve_execution_mode(
    *,
    purpose: str,
    requested_env: str | None = None,
    env: Mapping[str, str] | None = None,
) -> ExecutionMode:
    env_map = dict(env or {})
    purpose = purpose.strip().lower()

    # Defaults are purpose-specific. They intentionally do not require changing .env.
    if purpose in {"backtest_data", "historical_collection", "collect_intraday_90d"}:
        kiwoom_env = normalize_trading_env(requested_env or env_map.get("BACKTEST_KIWOOM_ENV") or "mock")
        return ExecutionMode(
            purpose=purpose,
            kiwoom_env=kiwoom_env,
            order_mode="none",
            can_collect_history=True,
            can_collect_live_snapshot=False,
            can_write_simulated_orders=False,
            can_call_real_order_api=False,
            reason="historical/backtest data collection only; no order side effects",
        )

    if purpose in {"live_data", "snapshot", "collect_current_session_snapshots"}:
        kiwoom_env = normalize_trading_env(requested_env or env_map.get("LIVE_DATA_KIWOOM_ENV") or env_map.get("TRADING_ENV") or "mock")
        return ExecutionMode(
            purpose=purpose,
            kiwoom_env=kiwoom_env,
            order_mode="none",
            can_collect_history=False,
            can_collect_live_snapshot=True,
            can_write_simulated_orders=False,
            can_call_real_order_api=False,
            reason="current-session observation only; no order side effects",
        )

    if purpose in {"paper", "paper_order", "simulate_approved_orders"}:
        kiwoom_env = normalize_trading_env(requested_env or env_map.get("PAPER_KIWOOM_ENV") or "mock")
        return ExecutionMode(
            purpose=purpose,
            kiwoom_env=kiwoom_env,
            order_mode="paper_only",
            can_collect_history=False,
            can_collect_live_snapshot=False,
            can_write_simulated_orders=True,
            can_call_real_order_api=False,
            reason="paper/simulated order records only; never calls Kiwoom real order API",
        )

    if purpose in {"real", "real_order", "approved_real_order_execution"}:
        kiwoom_env = normalize_trading_env(requested_env or env_map.get("REAL_KIWOOM_ENV") or "prod")
        real_enabled = all(
            str(env_map.get(k, "")).strip().lower() in {"1", "true", "yes", "enabled"}
            for k in ["REAL_ORDER_ENABLED", "USER_CONFIRMED_REAL_ORDER", "READINESS_REAL_ORDER_GATE"]
        )
        return ExecutionMode(
            purpose=purpose,
            kiwoom_env=kiwoom_env,
            order_mode="real" if real_enabled else "blocked",
            can_collect_history=False,
            can_collect_live_snapshot=False,
            can_write_simulated_orders=False,
            can_call_real_order_api=real_enabled and kiwoom_env == "prod",
            reason="real order requires prod plus REAL_ORDER_ENABLED/USER_CONFIRMED_REAL_ORDER/READINESS_REAL_ORDER_GATE",
        )

    return ExecutionMode(
        purpose=purpose,
        kiwoom_env=normalize_trading_env(requested_env or env_map.get("TRADING_ENV") or "mock"),
        order_mode="none",
        can_collect_history=False,
        can_collect_live_snapshot=False,
        can_write_simulated_orders=False,
        can_call_real_order_api=False,
        reason="unknown purpose defaults to no side effects",
    )


def redacted_mode_dict(mode: ExecutionMode) -> dict[str, object]:
    return {
        "purpose": mode.purpose,
        "kiwoom_env": mode.kiwoom_env,
        "order_mode": mode.order_mode,
        "can_collect_history": mode.can_collect_history,
        "can_collect_live_snapshot": mode.can_collect_live_snapshot,
        "can_write_simulated_orders": mode.can_write_simulated_orders,
        "can_call_real_order_api": mode.can_call_real_order_api,
        "reason": mode.reason,
    }


def real_order_blocking_conditions(env: Mapping[str, str] | None = None) -> list[str]:
    mode = resolve_execution_mode(purpose="real", env=env)
    blocks: list[str] = []
    if mode.kiwoom_env != "prod":
        blocks.append("real_order_requires_prod_kiwoom_env")
    if not mode.can_call_real_order_api:
        blocks.append("real_order_multi_key_gate_not_enabled")
    return blocks
