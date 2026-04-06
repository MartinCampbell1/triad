"""Unix socket listener for Claude Code hook events."""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path
from typing import Any, Awaitable, Callable


HookEventHandler = Callable[[dict[str, Any]], Awaitable[None]]


def default_socket_path() -> Path:
    override = os.environ.get("TRIAD_HOOKS_SOCKET", "").strip()
    if override:
        return Path(override).expanduser()
    return Path("/tmp/triad-hooks.sock")


class HooksListener:
    """Listen for newline-delimited JSON hook payloads on a Unix socket."""

    def __init__(
        self,
        on_event: HookEventHandler,
        socket_path: Path | None = None,
    ) -> None:
        self.on_event = on_event
        self.socket_path = socket_path or default_socket_path()
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            self.socket_path.unlink()
        self._server = await asyncio.start_unix_server(
            self._handle_connection,
            path=str(self.socket_path),
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self.socket_path.exists():
            self.socket_path.unlink()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            payload = await asyncio.wait_for(reader.read(65536), timeout=5.0)
            if not payload:
                return
            for raw_line in payload.decode("utf-8", errors="replace").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                event = self._parse_event(line)
                if event is None:
                    continue
                event["source"] = "hooks"
                await self.on_event(event)
        except (asyncio.TimeoutError, OSError, ConnectionError):
            return
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    @staticmethod
    def _parse_event(line: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
        return {"hook": "message", "payload": parsed}
