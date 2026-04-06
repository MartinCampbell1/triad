"""Interactive Claude PTY session manager."""
from __future__ import annotations

import asyncio
import contextlib
import fcntl
import os
import pty
import re
import signal
import struct
import termios
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Sequence


StreamEventHandler = Callable[[dict[str, Any]], Awaitable[None]]

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\].*?\x07|\x1b[()][AB012]|\r")

CHROME_PATTERNS = (
    "Press ",
    "Ctrl+",
    "Esc ",
    "╭",
    "╰",
    "│",
    "─",
    "⏳",
    "●",
    "◐",
    "◑",
    "◒",
    "◓",
)


@dataclass(slots=True)
class ClaudePTY:
    """Run Claude interactively in a hidden PTY and surface stream events."""

    workdir: Path
    on_event: StreamEventHandler
    command: Sequence[str] = field(default_factory=lambda: ("claude",))
    env: dict[str, str] | None = None
    cols: int = 120
    rows: int = 32
    _master_fd: int | None = None
    _child_pid: int | None = None
    _reader_task: asyncio.Task | None = None
    _exit_task: asyncio.Task | None = None
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
                os.close(slave_fd)
                os.chdir(self.workdir)
                os.execvpe(self.command[0], list(self.command), self._build_env())
            except Exception:
                os._exit(127)
        os.close(slave_fd)
        self._master_fd = master_fd
        self._child_pid = pid
        self._running = True
        self._reader_task = asyncio.create_task(self._read_loop())
        self._exit_task = asyncio.create_task(self._watch_exit())

    async def send(self, text: str) -> None:
        await self.write((text.rstrip("\n") + "\n").encode("utf-8"))

    async def write(self, data: bytes) -> None:
        if self._master_fd is None:
            raise RuntimeError("Claude PTY is not running")
        if not data:
            return
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
                await asyncio.to_thread(os.write, self._master_fd, b"/exit\n")
        if self._child_pid is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(self._child_pid, signal.SIGTERM)
        if self._reader_task is not None:
            self._reader_task.cancel()
        if self._exit_task is not None:
            self._exit_task.cancel()
        if self._master_fd is not None:
            with contextlib.suppress(OSError):
                os.close(self._master_fd)
        self._master_fd = None

    async def _read_loop(self) -> None:
        if self._master_fd is None:
            return
        while self._running:
            try:
                raw = await asyncio.to_thread(os.read, self._master_fd, 8192)
            except OSError:
                break
            if not raw:
                break
            cleaned = ANSI_ESCAPE.sub("", raw.decode("utf-8", errors="replace"))
            text = cleaned.strip()
            if text and not self._is_chrome(text):
                await self.on_event(
                    {
                        "type": "text_delta",
                        "source": "pty",
                        "provider": "claude",
                        "delta": cleaned,
                    }
                )

    async def _watch_exit(self) -> None:
        if self._child_pid is None:
            return
        try:
            _, status = await asyncio.to_thread(os.waitpid, self._child_pid, 0)
        except OSError as exc:
            await self.on_event(
                {
                    "type": "run_failed",
                    "source": "pty",
                    "provider": "claude",
                    "error": str(exc),
                }
            )
            return

        if os.WIFEXITED(status):
            returncode: int | None = os.WEXITSTATUS(status)
        elif os.WIFSIGNALED(status):
            returncode = -os.WTERMSIG(status)
        else:
            returncode = None

        if self._running:
            await self.on_event(
                {
                    "type": "run_completed" if returncode in (None, 0) else "run_failed",
                    "source": "pty",
                    "provider": "claude",
                    "returncode": returncode,
                }
            )

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        if self.env:
            env.update(self.env)
        env.setdefault("TERM", "xterm-256color")
        env.setdefault("COLORTERM", "truecolor")
        env.setdefault("HOME", str(Path.home()))
        return env

    def _apply_winsize(self, fd: int) -> None:
        winsize = struct.pack("HHHH", self.rows, self.cols, 0, 0)
        with contextlib.suppress(OSError):
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    @staticmethod
    def _is_chrome(text: str) -> bool:
        return any(pattern in text for pattern in CHROME_PATTERNS)
