from __future__ import annotations

import base64
import contextlib
from pathlib import Path
from typing import Any

JsonValue = dict[str, Any]


def register_terminal_handlers(bridge: Any) -> None:
    @bridge.method("terminal.create")
    async def terminal_create(params: JsonValue) -> dict[str, Any]:
        manager = await bridge.runtime.get_terminal_manager()
        cwd = str(params.get("cwd") or Path.home())
        title = str(params.get("title") or "").strip() or None
        cols = int(params.get("cols") or 120)
        rows = int(params.get("rows") or 24)
        session = await manager.create(cwd=cwd, cols=cols, rows=rows, title=title)
        return {"terminal_id": session.terminal_id, "session": session.describe()}

    @bridge.method("terminal.list")
    async def terminal_list(_: JsonValue) -> dict[str, Any]:
        manager = await bridge.runtime.get_terminal_manager()
        return {"sessions": manager.list_sessions()}

    @bridge.method("terminal.input")
    async def terminal_input(params: JsonValue) -> dict[str, Any]:
        terminal_id = str(params.get("terminal_id", ""))
        if not terminal_id:
            raise ValueError("terminal_id is required")
        raw = str(params.get("data", ""))
        payload = base64.b64decode(raw) if raw else b""
        return await bridge.runtime.handle_terminal_input(terminal_id, payload)

    @bridge.method("terminal.resize")
    async def terminal_resize(params: JsonValue) -> dict[str, Any]:
        terminal_id = str(params.get("terminal_id", ""))
        if not terminal_id:
            raise ValueError("terminal_id is required")
        cols = int(params.get("cols") or 120)
        rows = int(params.get("rows") or 24)
        return await bridge.runtime.handle_terminal_resize(terminal_id, cols=cols, rows=rows)

    @bridge.method("terminal.close")
    async def terminal_close(params: JsonValue) -> dict[str, Any]:
        terminal_id = str(params.get("terminal_id", ""))
        if not terminal_id:
            raise ValueError("terminal_id is required")
        manager = await bridge.runtime.get_terminal_manager()
        session = manager.get_session(terminal_id)
        if session is not None and session.kind == "provider" and session.linked_session_id:
            with contextlib.suppress(Exception):
                await bridge.runtime.stop_session(session.linked_session_id)
        await manager.close(terminal_id)
        if session is not None and session.kind == "provider" and session.linked_session_id:
            runtime = bridge.runtime._sessions.get(session.linked_session_id)
            if runtime is not None and runtime.linked_terminal_id == terminal_id:
                runtime.linked_terminal_id = None
        return {"status": "ok"}

    @bridge.method("terminal.clear")
    async def terminal_clear(params: JsonValue) -> dict[str, Any]:
        terminal_id = str(params.get("terminal_id", ""))
        if not terminal_id:
            raise ValueError("terminal_id is required")
        manager = await bridge.runtime.get_terminal_manager()
        await manager.clear(terminal_id)
        return {"status": "ok"}


__all__ = ["register_terminal_handlers"]
