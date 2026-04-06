from __future__ import annotations

import contextlib
import inspect
import sys
from typing import Any

from ..hooks_listener import default_socket_path


async def build_runtime_diagnostics(runtime: Any) -> dict[str, Any]:
    active_terminals: list[str] = []
    if getattr(runtime, "_terminal_manager", None) is not None:
        with contextlib.suppress(Exception):
            active = runtime._terminal_manager.list_active()
            active_terminals = await active if inspect.isawaitable(active) else active

    return {
        "version": "0.1.0",
        "python_version": sys.version,
        "triad_home": str(runtime.config.triad_home),
        "db_path": str(runtime.config.db_path),
        "providers": {
            provider: runtime.account_manager.pool_status(provider)
            for provider in ("claude", "codex", "gemini")
        },
        "active_claude_sessions": [
            session_id
            for session_id, active_runtime in runtime._sessions.items()
            if active_runtime.pty is not None
        ],
        "active_sessions": [
            {
                "id": active_runtime.session_id,
                "mode": active_runtime.mode,
                "provider": active_runtime.provider,
                "project_path": active_runtime.project_path,
                "state": active_runtime.state,
            }
            for active_runtime in runtime._sessions.values()
        ],
        "active_terminals": active_terminals,
        "active_file_watches": runtime._file_watcher.snapshot() if runtime._file_watcher is not None else [],
        "hooks_socket": str(runtime._hook_listener.socket_path if runtime._hook_listener else default_socket_path()),
    }
