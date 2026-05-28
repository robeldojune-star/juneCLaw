"""Shared JSON result helpers for n8n/Hermes trading workflows.

All stage scripts should return this shape so n8n can branch consistently.
Secrets are never included in results.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class WorkflowStep:
    name: str
    ok: bool
    status: str = "completed"
    summary: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    blocking_conditions: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class WorkflowResult:
    ok: bool
    workflow: str
    stage: str
    status: str
    started_at: str
    finished_at: str
    model_grade: str = "none"
    steps: list[WorkflowStep] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)
    blocking_conditions: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_result(
    *,
    workflow: str,
    stage: str,
    started_at: str,
    model_grade: str = "none",
    steps: list[WorkflowStep] | None = None,
    summary: dict[str, Any] | None = None,
    alerts: list[str] | None = None,
    blocking_conditions: list[str] | None = None,
    next_actions: list[str] | None = None,
) -> WorkflowResult:
    steps = steps or []
    blocking_conditions = blocking_conditions or []
    alerts = alerts or []
    step_blocks: list[str] = []
    for step in steps:
        step_blocks.extend(step.blocking_conditions)
    all_blocks = list(dict.fromkeys(blocking_conditions + step_blocks))
    steps_ok = all(step.ok for step in steps)
    ok = steps_ok and not all_blocks
    status = "completed" if ok else "blocked" if all_blocks else "failed"
    return WorkflowResult(
        ok=ok,
        workflow=workflow,
        stage=stage,
        status=status,
        started_at=started_at,
        finished_at=utc_now_iso(),
        model_grade=model_grade,
        steps=steps,
        summary=summary or {},
        alerts=alerts,
        blocking_conditions=all_blocks,
        next_actions=next_actions or [],
    )
