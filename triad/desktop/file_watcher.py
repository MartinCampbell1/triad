"""Best-effort Claude session file watcher for authoritative assistant history."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable


WatcherEventHandler = Callable[[dict[str, Any]], Awaitable[None]]


def default_claude_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


@dataclass(slots=True)
class SessionFileBinding:
    session_id: str
    project_path: str
    project_dir: Path
    started_at: float
    prompt_hint: str = ""
    bound_file: Path | None = None
    offset: int = 0
    partial_line: str = ""
    seen_message_ids: set[str] = field(default_factory=set)
    rebind_from_end: bool = False


class ClaudeSessionWatcher:
    """Poll Claude's local session files and emit clean assistant messages."""

    def __init__(
        self,
        on_event: WatcherEventHandler,
        *,
        claude_projects_dir: Path | None = None,
        poll_interval: float = 0.6,
    ) -> None:
        self.on_event = on_event
        self.claude_projects_dir = claude_projects_dir or default_claude_projects_dir()
        self.poll_interval = poll_interval
        self._bindings: dict[str, SessionFileBinding] = {}
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._bindings.clear()

    def watch_session(
        self, session_id: str, project_path: str, *, prompt_hint: str | None = None
    ) -> None:
        normalized_project = str(Path(project_path).expanduser().resolve())
        existing = self._bindings.get(session_id)
        if existing is not None and existing.project_path == normalized_project:
            existing.started_at = time.time()
            if prompt_hint:
                existing.prompt_hint = prompt_hint
                existing.bound_file = None
                existing.offset = 0
                existing.partial_line = ""
                existing.rebind_from_end = True
            return
        self._bindings[session_id] = SessionFileBinding(
            session_id=session_id,
            project_path=normalized_project,
            project_dir=self.claude_projects_dir
            / self.project_path_to_storage_dir(normalized_project),
            started_at=time.time(),
            prompt_hint=prompt_hint or "",
        )

    def unwatch_session(self, session_id: str) -> None:
        self._bindings.pop(session_id, None)

    def snapshot(self) -> list[dict[str, str]]:
        return [
            {
                "session_id": binding.session_id,
                "project_path": binding.project_path,
                "project_dir": str(binding.project_dir),
                "bound_file": str(binding.bound_file) if binding.bound_file else "",
            }
            for binding in self._bindings.values()
        ]

    async def scan_once(self) -> None:
        for binding in list(self._bindings.values()):
            await self._scan_binding(binding)

    async def _poll_loop(self) -> None:
        try:
            while self._running:
                await self.scan_once()
                await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            raise

    async def _scan_binding(self, binding: SessionFileBinding) -> None:
        if binding.bound_file is None or not binding.bound_file.exists():
            self._bind_file(binding)
        if binding.bound_file is None or not binding.bound_file.exists():
            return

        file_path = binding.bound_file
        try:
            size = file_path.stat().st_size
        except OSError:
            return

        if size < binding.offset:
            binding.offset = 0
            binding.partial_line = ""

        if size == binding.offset:
            return

        try:
            with file_path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(binding.offset)
                chunk = handle.read()
                binding.offset = handle.tell()
        except OSError:
            return

        if not chunk:
            return

        payload = binding.partial_line + chunk
        complete_lines = payload.splitlines(keepends=True)
        if complete_lines and not complete_lines[-1].endswith(("\n", "\r")):
            binding.partial_line = complete_lines.pop()
        else:
            binding.partial_line = ""

        for raw_line in complete_lines:
            line = raw_line.strip()
            if not line:
                continue
            event = self._parse_line(binding, line)
            if event is None:
                continue
            await self.on_event(event)

    def _bind_file(self, binding: SessionFileBinding) -> None:
        if not binding.project_dir.is_dir():
            return

        claimed = {
            current.bound_file
            for current in self._bindings.values()
            if current.session_id != binding.session_id
            and current.bound_file is not None
        }
        candidates = sorted(
            (
                candidate
                for candidate in binding.project_dir.glob("*.jsonl")
                if candidate.is_file()
            ),
            key=lambda candidate: self._candidate_score(candidate, binding, claimed),
            reverse=True,
        )
        if not candidates:
            return

        chosen = candidates[0]
        binding.bound_file = chosen
        try:
            chosen_stat = chosen.stat()
            recent_enough = chosen_stat.st_mtime >= binding.started_at - 30
        except OSError:
            binding.bound_file = None
            recent_enough = False
            chosen_stat = None
        binding.offset = (
            chosen_stat.st_size
            if binding.rebind_from_end and chosen_stat is not None
            else (
                0
                if recent_enough
                else (chosen_stat.st_size if chosen_stat is not None else 0)
            )
        )
        binding.partial_line = ""
        binding.rebind_from_end = False

    def _parse_line(
        self,
        binding: SessionFileBinding,
        line: str,
    ) -> dict[str, Any] | None:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None

        message = parsed.get("message")
        if not isinstance(message, dict):
            return None
        if str(message.get("role")) != "assistant":
            return None

        content = self._extract_assistant_text(message)
        if not content:
            return None

        message_id = self._message_identity(parsed, message, line)
        if message_id in binding.seen_message_ids:
            return None

        binding.seen_message_ids.add(message_id)
        return {
            "type": "authoritative_message",
            "source": "file_watcher",
            "provider": "claude",
            "session_id": binding.session_id,
            "role": "assistant",
            "content": content,
            "timestamp": parsed.get("timestamp"),
            "message_id": message_id,
            "claude_session_id": parsed.get("sessionId"),
            "session_file": str(binding.bound_file) if binding.bound_file else "",
        }

    @staticmethod
    def _extract_assistant_text(message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()

    @staticmethod
    def _message_identity(
        parsed: dict[str, Any], message: dict[str, Any], line: str
    ) -> str:
        candidates = (
            parsed.get("uuid"),
            message.get("id"),
            parsed.get("requestId"),
        )
        for candidate in candidates:
            value = str(candidate or "").strip()
            if value:
                return value
        return hashlib.sha1(line.encode("utf-8", errors="replace")).hexdigest()

    @staticmethod
    def project_path_to_storage_dir(project_path: str) -> str:
        normalized = str(Path(project_path).expanduser().resolve())
        return re.sub(r"[\\/]+", "-", normalized)

    def _candidate_score(
        self,
        candidate: Path,
        binding: SessionFileBinding,
        claimed: set[Path],
    ) -> tuple[int, float]:
        claimed_penalty = 0 if candidate not in claimed else -10
        prompt_bonus = 0
        if binding.prompt_hint:
            prompt_bonus = self._candidate_prompt_bonus(candidate, binding.prompt_hint)
        try:
            mtime = candidate.stat().st_mtime
        except OSError:
            mtime = 0.0
        return (claimed_penalty + prompt_bonus, mtime)

    @staticmethod
    def _candidate_prompt_bonus(candidate: Path, prompt_hint: str) -> int:
        normalized_prompt = " ".join(prompt_hint.split()).strip()
        if not normalized_prompt:
            return 0
        try:
            with candidate.open("rb") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(max(0, size - 65536))
                tail = handle.read().decode("utf-8", errors="replace")
        except OSError:
            return 0

        if normalized_prompt in tail:
            return 100
        compact_prompt = normalized_prompt[:160]
        if compact_prompt and compact_prompt in tail:
            return 80
        return 0
