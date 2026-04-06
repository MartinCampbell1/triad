"""PTY-based terminal session manager for the Triad desktop client."""
from __future__ import annotations

import asyncio
import contextlib
import fcntl
import os
import pty
import signal
import struct
import termios
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Sequence


TerminalOutputHandler = Callable[[str, bytes], Awaitable[None]]

_DEFAULT_SHELL = os.environ.get("SHELL", "/bin/zsh")
_READ_SIZE = 8192
_MAX_BUFFER_CHARS = 200000

@dataclass(slots=True)
class TerminalSession:
    """One interactive shell running inside a PTY."""

    terminal_id: str
    cwd: Path
    on_output: TerminalOutputHandler
    command: Sequence[str] = field(default_factory=lambda: (_DEFAULT_SHELL, "-l"))
    env: dict[str, str] | None = None
    title: str | None = None
    kind: str = "shell"
    virtual: bool = False
    linked_session_id: str | None = None
    linked_run_id: str | None = None
    linked_provider: str | None = None
    transcript_mode: str | None = None
    cols: int = 80
    rows: int = 24
    created_at: str = field(default_factory=lambda: "")
    updated_at: str = field(default_factory=lambda: "")
    last_output_at: str | None = None
    status: str = "starting"
    buffer: str = ""
    _master_fd: int | None = None
    _child_pid: int | None = None
    _reader_task: asyncio.Task | None = None
    _wait_task: asyncio.Task | None = None
    _running: bool = False

    async def start(self) -> None:
        if self._running:
            return
        now = self._timestamp()
        self.created_at = self.created_at or now
        self.updated_at = now
        self.status = "ready"

        if self.virtual:
            return

        master_fd, slave_fd = pty.openpty()
        self._apply_winsize(slave_fd)

        pid = os.fork()
        if pid == 0:
            try:
                os.close(master_fd)
                os.setsid()
                os.dup2(slave_fd, 0)
                os.dup2(slave_fd, 1)
                os.dup2(slave_fd, 2)
                with contextlib.suppress(OSError):
                    os.close(slave_fd)
                os.chdir(self.cwd)
                self._exec_child()
            except Exception:
                os._exit(127)

        os.close(slave_fd)
        self._master_fd = master_fd
        self._child_pid = pid
        self._running = True
        self._reader_task = asyncio.create_task(self._read_loop())
        self._wait_task = asyncio.create_task(self._wait_for_exit())

    async def write(self, data: bytes) -> None:
        if not self._running or self._master_fd is None:
            raise RuntimeError("Terminal session is not running")
        self.touch()
        await asyncio.to_thread(os.write, self._master_fd, data)

    async def resize(self, cols: int, rows: int) -> None:
        if cols <= 0 or rows <= 0:
            raise ValueError("Terminal size must be positive")
        self.cols = cols
        self.rows = rows
        self.touch()
        if self._master_fd is None:
            return
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        await asyncio.to_thread(
            fcntl.ioctl,
            self._master_fd,
            termios.TIOCSWINSZ,
            winsize,
        )

    async def stop(self) -> None:
        if self.virtual:
            self.status = "unavailable"
            self.touch()
            return

        if not self._running:
            return
        self._running = False
        self.status = "unavailable"
        self.touch()

        if self._master_fd is not None:
            with contextlib.suppress(OSError):
                await asyncio.to_thread(os.write, self._master_fd, b"exit\n")

        if self._child_pid is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(self._child_pid, signal.SIGTERM)

        await self._cancel_tasks()
        await self._reap_child()
        self._close_master()

    async def _read_loop(self) -> None:
        if self._master_fd is None:
            return

        while self._running:
            try:
                data = await asyncio.to_thread(os.read, self._master_fd, _READ_SIZE)
            except OSError:
                break
            if not data:
                break
            self.append_output(data)
            await self.on_output(self.terminal_id, data)

    async def _wait_for_exit(self) -> None:
        if self._child_pid is None:
            return
        try:
            await asyncio.to_thread(os.waitpid, self._child_pid, 0)
        except OSError:
            pass
        finally:
            self._running = False
            self.status = "unavailable"
            self.touch()
            self._close_master()

    async def _cancel_tasks(self) -> None:
        tasks = [task for task in (self._reader_task, self._wait_task) if task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._reader_task = None
        self._wait_task = None

    async def _reap_child(self) -> None:
        if self._child_pid is None:
            return
        with contextlib.suppress(OSError):
            await asyncio.to_thread(os.waitpid, self._child_pid, os.WNOHANG)
        self._child_pid = None

    def _close_master(self) -> None:
        if self._master_fd is None:
            return
        with contextlib.suppress(OSError):
            os.close(self._master_fd)
        self._master_fd = None

    def append_output(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        if not text:
            return
        self.buffer = (self.buffer + text)[-_MAX_BUFFER_CHARS :]
        now = self._timestamp()
        self.last_output_at = now
        self.updated_at = now

    def touch(self) -> None:
        self.updated_at = self._timestamp()

    def clear(self) -> None:
        self.buffer = ""
        self.last_output_at = None
        self.touch()

    def snapshot(self) -> str:
        return self.buffer

    def describe(self) -> dict[str, Any]:
        return {
            "terminal_id": self.terminal_id,
            "title": self.title or self.cwd.name or "Shell",
            "cwd": str(self.cwd),
            "command": list(self.command),
            "shell": self.command[0] if self.command else _DEFAULT_SHELL,
            "kind": self.kind,
            "virtual": self.virtual,
            "linked_session_id": self.linked_session_id,
            "linked_run_id": self.linked_run_id,
            "linked_provider": self.linked_provider,
            "transcript_mode": self.transcript_mode,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_output_at": self.last_output_at,
            "snapshot": self.snapshot(),
        }

    @staticmethod
    def _timestamp() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

    def _apply_winsize(self, slave_fd: int) -> None:
        winsize = struct.pack("HHHH", self.rows, self.cols, 0, 0)
        with contextlib.suppress(OSError):
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

    def _exec_child(self) -> None:
        env = dict(os.environ)
        if self.env:
            env.update(self.env)
        env.setdefault("TERM", "xterm-256color")
        env.setdefault("COLORTERM", "truecolor")
        os.execvpe(self.command[0], list(self.command), env)


class TerminalManager:
    """Manage multiple PTY-backed shell sessions for the desktop bridge."""

    def __init__(self, on_output: TerminalOutputHandler):
        self.on_output = on_output
        self._sessions: dict[str, TerminalSession] = {}

    async def create(
        self,
        cwd: str | Path,
        *,
        command: Sequence[str] | None = None,
        env: dict[str, str] | None = None,
        title: str | None = None,
        kind: str = "shell",
        virtual: bool = False,
        linked_session_id: str | None = None,
        linked_run_id: str | None = None,
        linked_provider: str | None = None,
        transcript_mode: str | None = None,
        cols: int = 80,
        rows: int = 24,
        terminal_id: str | None = None,
    ) -> TerminalSession:
        session_id = terminal_id or f"term_{uuid.uuid4().hex[:8]}"
        resolved_cwd = Path(cwd).expanduser().resolve()
        same_cwd_count = sum(
            1
            for session in self._sessions.values()
            if session.cwd == resolved_cwd and session.kind == kind
        )
        session_title = title or self._default_title(resolved_cwd, same_cwd_count + 1)
        session = TerminalSession(
            terminal_id=session_id,
            cwd=resolved_cwd,
            on_output=self.on_output,
            command=command or (_DEFAULT_SHELL, "-l"),
            env=env,
            title=session_title,
            kind=kind,
            virtual=virtual,
            linked_session_id=linked_session_id,
            linked_run_id=linked_run_id,
            linked_provider=linked_provider,
            transcript_mode=transcript_mode,
            cols=cols,
            rows=rows,
        )
        await session.start()
        self._sessions[session_id] = session
        return session

    async def ensure_provider_session(
        self,
        *,
        session_id: str,
        cwd: str | Path,
        title: str,
        provider: str,
        run_id: str | None = None,
        terminal_id: str | None = None,
    ) -> TerminalSession:
        linked_terminal_id = terminal_id or f"live_{session_id}"
        existing = self._sessions.get(linked_terminal_id)
        if existing is not None:
            existing.cwd = Path(cwd).expanduser().resolve()
            existing.title = title
            existing.kind = "provider"
            existing.virtual = True
            existing.linked_session_id = session_id
            existing.linked_run_id = run_id
            existing.linked_provider = provider
            existing.transcript_mode = "partial"
            existing.status = "ready"
            existing.touch()
            return existing

        return await self.create(
            cwd=cwd,
            title=title,
            kind="provider",
            virtual=True,
            linked_session_id=session_id,
            linked_run_id=run_id,
            linked_provider=provider,
            transcript_mode="partial",
            terminal_id=linked_terminal_id,
        )

    async def write(self, terminal_id: str, data: bytes) -> None:
        session = self._sessions.get(terminal_id)
        if session is None:
            raise KeyError(f"Unknown terminal session: {terminal_id}")
        await session.write(data)

    async def resize(self, terminal_id: str, cols: int, rows: int) -> None:
        session = self._sessions.get(terminal_id)
        if session is None:
            raise KeyError(f"Unknown terminal session: {terminal_id}")
        await session.resize(cols, rows)

    async def close(self, terminal_id: str) -> None:
        session = self._sessions.pop(terminal_id, None)
        if session is None:
            return
        await session.stop()

    async def clear(self, terminal_id: str) -> None:
        session = self._sessions.get(terminal_id)
        if session is None:
            raise KeyError(f"Unknown terminal session: {terminal_id}")
        session.clear()

    async def capture_output(self, terminal_id: str, data: bytes) -> None:
        session = self._sessions.get(terminal_id)
        if session is None:
            raise KeyError(f"Unknown terminal session: {terminal_id}")
        session.append_output(data)
        await self.on_output(terminal_id, data)

    def update_session(
        self,
        terminal_id: str,
        *,
        title: str | None = None,
        status: str | None = None,
        linked_run_id: str | None = None,
        linked_provider: str | None = None,
        transcript_mode: str | None = None,
    ) -> TerminalSession:
        session = self._sessions.get(terminal_id)
        if session is None:
            raise KeyError(f"Unknown terminal session: {terminal_id}")
        if title is not None:
            session.title = title
        if status is not None:
            session.status = status
        if linked_run_id is not None:
            session.linked_run_id = linked_run_id
        if linked_provider is not None:
            session.linked_provider = linked_provider
        if transcript_mode is not None:
            session.transcript_mode = transcript_mode
        session.touch()
        return session

    async def close_all(self) -> None:
        sessions = list(self._sessions.items())
        self._sessions.clear()
        for _, session in sessions:
            with contextlib.suppress(Exception):
                await session.stop()

    def get_session(self, terminal_id: str) -> TerminalSession | None:
        return self._sessions.get(terminal_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        sessions = sorted(
            self._sessions.values(),
            key=lambda session: (session.updated_at, session.created_at, session.terminal_id),
            reverse=True,
        )
        return [session.describe() for session in sessions]

    def list_active(self) -> list[str]:
        return list(self._sessions.keys())

    @staticmethod
    def _default_title(cwd: Path, index: int) -> str:
        label = cwd.name or cwd.anchor or "Shell"
        return f"{label} {index}"


__all__ = ["TerminalManager", "TerminalSession", "TerminalOutputHandler"]
