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
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Sequence


TerminalOutputHandler = Callable[[str, bytes], Awaitable[None]]

_DEFAULT_SHELL = os.environ.get("SHELL", "/bin/zsh")
_READ_SIZE = 8192


@dataclass(slots=True)
class TerminalSession:
    """One interactive shell running inside a PTY."""

    terminal_id: str
    cwd: Path
    on_output: TerminalOutputHandler
    command: Sequence[str] = field(default_factory=lambda: (_DEFAULT_SHELL, "-l"))
    env: dict[str, str] | None = None
    cols: int = 80
    rows: int = 24
    _master_fd: int | None = None
    _child_pid: int | None = None
    _reader_task: asyncio.Task | None = None
    _wait_task: asyncio.Task | None = None
    _running: bool = False

    async def start(self) -> None:
        if self._running:
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
        await asyncio.to_thread(os.write, self._master_fd, data)

    async def resize(self, cols: int, rows: int) -> None:
        if cols <= 0 or rows <= 0:
            raise ValueError("Terminal size must be positive")
        self.cols = cols
        self.rows = rows
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
        if not self._running:
            return
        self._running = False

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
        cols: int = 80,
        rows: int = 24,
        terminal_id: str | None = None,
    ) -> str:
        session_id = terminal_id or f"term_{uuid.uuid4().hex[:8]}"
        session = TerminalSession(
            terminal_id=session_id,
            cwd=Path(cwd).expanduser().resolve(),
            on_output=self.on_output,
            command=command or (_DEFAULT_SHELL, "-l"),
            env=env,
            cols=cols,
            rows=rows,
        )
        await session.start()
        self._sessions[session_id] = session
        return session_id

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

    async def close_all(self) -> None:
        sessions = list(self._sessions.items())
        self._sessions.clear()
        for _, session in sessions:
            with contextlib.suppress(Exception):
                await session.stop()

    def list_active(self) -> list[str]:
        return list(self._sessions.keys())


__all__ = ["TerminalManager", "TerminalSession", "TerminalOutputHandler"]
