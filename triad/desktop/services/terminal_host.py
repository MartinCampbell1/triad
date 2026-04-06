from __future__ import annotations

from pathlib import Path
from typing import Any


def terminal_host_terminal_id(session_id: str) -> str:
    return f"live_{session_id}"


def terminal_host_title(session_title: str, provider: str) -> str:
    normalized_title = " ".join(session_title.strip().split()) or "Session"
    label = provider.strip().title() or "Provider"
    return f"{label} live · {normalized_title[:52]}"


def build_terminal_host_metadata(
    runtime: Any,
    terminal_session: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    terminal_id = getattr(runtime, "linked_terminal_id", None)
    active_run_id = getattr(runtime, "active_run_id", None) or (terminal_session or {}).get("linked_run_id")
    transcript_mode = str(getattr(runtime, "transcript_capture", "typed") or "typed")
    if not terminal_id and not terminal_session:
        return None

    status = str((terminal_session or {}).get("status") or ("ready" if active_run_id else "unavailable"))
    terminal_cwd = (terminal_session or {}).get("cwd")
    if not terminal_cwd and getattr(runtime, "project_path", None):
        terminal_cwd = str(Path(getattr(runtime, "project_path")).expanduser().resolve())
    return {
        "terminal_id": terminal_id or (terminal_session or {}).get("terminal_id"),
        "terminal_title": (terminal_session or {}).get("title") or None,
        "terminal_cwd": terminal_cwd,
        "terminal_status": status,
        "live": bool(active_run_id and status == "ready"),
        "transcript_mode": transcript_mode if transcript_mode in {"partial", "typed", "live", "full"} else "typed",
        "linked_run_id": active_run_id,
    }
