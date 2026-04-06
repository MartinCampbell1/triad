from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RunLifecycleContext:
    session_id: str
    run_id: str | None
    provider: str
    role: str
    policy_role: str | None = None
    sandbox: str | None = None
    workdir: Path | None = None


def build_run_started_event(context: RunLifecycleContext) -> dict[str, Any]:
    event: dict[str, Any] = {
        "session_id": context.session_id,
        "run_id": context.run_id,
        "type": "system",
        "provider": context.provider,
        "role": context.role,
        "run_phase": "started",
        "content": f"{context.provider.title()} {context.role} is running",
    }
    if context.policy_role:
        event["policy_role"] = context.policy_role
    if context.sandbox:
        event["sandbox"] = context.sandbox
    if context.workdir is not None:
        event["workdir"] = str(context.workdir)
    return event


def build_run_completed_event(
    context: RunLifecycleContext,
    *,
    stdout: str,
    stderr: str,
    returncode: int | None,
    timed_out: bool,
    rate_limited: bool,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "session_id": context.session_id,
        "run_id": context.run_id,
        "type": "run_completed",
        "provider": context.provider,
        "role": context.role,
        "run_phase": "completed",
        "stdout": stdout,
        "stderr": stderr,
        "returncode": returncode,
        "timed_out": timed_out,
        "rate_limited": rate_limited,
    }
    if context.policy_role:
        event["policy_role"] = context.policy_role
    if context.sandbox:
        event["sandbox"] = context.sandbox
    if context.workdir is not None:
        event["workdir"] = str(context.workdir)
    return event


def build_run_failed_event(
    context: RunLifecycleContext,
    *,
    error: str,
    stdout: str,
    stderr: str,
    returncode: int | None,
    timed_out: bool,
    rate_limited: bool,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "session_id": context.session_id,
        "run_id": context.run_id,
        "type": "run_failed",
        "provider": context.provider,
        "role": context.role,
        "run_phase": "failed",
        "error": error,
        "stdout": stdout,
        "stderr": stderr,
        "returncode": returncode,
        "timed_out": timed_out,
        "rate_limited": rate_limited,
    }
    if context.policy_role:
        event["policy_role"] = context.policy_role
    if context.sandbox:
        event["sandbox"] = context.sandbox
    if context.workdir is not None:
        event["workdir"] = str(context.workdir)
    return event
