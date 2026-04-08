"""JSON-RPC bridge between the Tauri desktop shell and Python backend."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import inspect
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from triad.core.accounts.manager import AccountManager
from triad.core.config import get_default_config_path, load_config
from triad.core.providers import get_adapter
from triad.core.providers.base import is_rate_limited

from .claude_pty import ClaudePTY
from .event_merger import EventMerger
from .event_schema import (
    CANONICAL_STREAM_EVENT_TYPES,
    canonical_event_type,
    normalize_stream_event,
)
from .file_watcher import ClaudeSessionWatcher
from .hooks_listener import HooksListener, default_socket_path
from .orchestrator import Orchestrator
from .search import SearchIndex
from .terminal_manager import TerminalManager

try:  # pragma: no cover - optional dependency fallback
    from triad.core.storage.ledger import Ledger as CoreLedger
except ModuleNotFoundError:  # pragma: no cover - environment fallback
    CoreLedger = None


JsonValue = dict[str, Any]
Handler = Callable[[JsonValue], Awaitable[Any]]


@dataclass(slots=True)
class SessionRuntime:
    session_id: str
    project_path: str
    mode: str
    provider: str
    title: str
    pty: ClaudePTY | None = None
    state: str = "active"


class MemoryLedger:
    """Fallback ledger when `aiosqlite` is unavailable."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._sessions: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._seq: dict[str, int] = {}
        self._projects: dict[str, dict[str, Any]] = {}
        self._closed = False
        self._db = None

    async def initialize(self) -> None:
        self._closed = False

    async def close(self) -> None:
        self._closed = True

    async def create_session(
        self,
        mode: str,
        task: str,
        config_json: str | None = None,
        *,
        title: str | None = None,
        project_path: str | None = None,
    ) -> str:
        session_id = f"ts_{uuid.uuid4().hex[:12]}"
        now = time.time()
        self._sessions[session_id] = {
            "id": session_id,
            "mode": mode,
            "task": task,
            "title": title,
            "project_path": project_path,
            "status": "running",
            "config_json": config_json,
            "created_at": now,
            "updated_at": now,
        }
        self._seq[session_id] = 0
        return session_id

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self._sessions.get(session_id)
        return dict(row) if row is not None else None

    async def list_sessions(
        self,
        limit: int = 50,
        *,
        project_path: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = sorted(
            self._sessions.values(), key=lambda row: row["updated_at"], reverse=True
        )
        if project_path is not None:
            rows = [row for row in rows if row.get("project_path") == project_path]
        return [dict(row) for row in rows[:limit]]

    async def update_session_status(self, session_id: str, status: str) -> None:
        row = self._sessions.get(session_id)
        if row is None:
            return
        row["status"] = status
        row["updated_at"] = time.time()

    async def log_event(
        self,
        session_id: str,
        event_type: str,
        agent: str | None = None,
        content: str | None = None,
        artifact_id: str | None = None,
    ) -> int:
        seq = self._seq.get(session_id, 0) + 1
        self._seq[session_id] = seq
        event = {
            "id": len(self._events) + 1,
            "session_id": session_id,
            "seq": seq,
            "event_type": event_type,
            "agent": agent,
            "content": content,
            "artifact_id": artifact_id,
            "ts": time.time(),
        }
        self._events.append(event)
        row = self._sessions.get(session_id)
        if row is not None:
            row["updated_at"] = event["ts"]
        return event["id"]

    async def append_event(
        self,
        session_id: str,
        event_type: str,
        data: dict[str, Any],
        *,
        provider: str | None = None,
        role: str | None = None,
        run_id: str | None = None,
        agent: str | None = None,
        content: str | None = None,
        artifact_id: str | None = None,
    ) -> int:
        seq = self._seq.get(session_id, 0) + 1
        self._seq[session_id] = seq
        event = {
            "id": len(self._events) + 1,
            "session_id": session_id,
            "seq": seq,
            "event_type": event_type,
            "agent": agent,
            "content": content,
            "artifact_id": artifact_id,
            "run_id": run_id,
            "provider": provider,
            "role": role,
            "data_json": json.dumps(data, ensure_ascii=False),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "ts": time.time(),
        }
        self._events.append(event)
        row = self._sessions.get(session_id)
        if row is not None:
            row["updated_at"] = event["ts"]
        return event["id"]

    async def update_session_title(self, session_id: str, title: str) -> None:
        row = self._sessions.get(session_id)
        if row is None:
            return
        row["title"] = title
        row["updated_at"] = time.time()

    async def count_events(self, session_id: str) -> int:
        return sum(1 for event in self._events if event["session_id"] == session_id)

    async def get_session_events(
        self, session_id: str, limit: int = 500
    ) -> list[dict[str, Any]]:
        rows = [
            event
            for event in sorted(self._events, key=lambda item: item["seq"])
            if event["session_id"] == session_id
        ][:limit]
        events: list[dict[str, Any]] = []
        for row in rows:
            data_json = row.get("data_json")
            data: dict[str, Any] = {}
            if data_json:
                try:
                    data = json.loads(str(data_json))
                except json.JSONDecodeError:
                    data = {"raw": str(data_json)}
            elif row.get("content"):
                data = {"content": row["content"]}
            events.append(
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "seq": row["seq"],
                    "run_id": row.get("run_id"),
                    "type": row.get("event_type"),
                    "provider": row.get("provider"),
                    "role": row.get("role"),
                    "agent": row.get("agent"),
                    "content": row.get("content"),
                    "artifact_id": row.get("artifact_id"),
                    "timestamp": row.get("timestamp"),
                    "ts": row.get("ts"),
                    "data": data,
                }
            )
        return events

    async def save_project(self, path: str, display_name: str, git_root: str) -> None:
        self._projects[path] = {
            "path": path,
            "display_name": display_name,
            "name": display_name,
            "git_root": git_root,
            "last_opened_at": time.time(),
        }

    async def list_projects(self) -> list[dict[str, Any]]:
        return sorted(
            (dict(project) for project in self._projects.values()),
            key=lambda row: row["last_opened_at"],
            reverse=True,
        )


class DesktopRuntime:
    """Owns persistent state and active session processes."""

    def __init__(self) -> None:
        self.config = load_config(get_default_config_path())
        self.account_manager = AccountManager(
            self.config.profiles_dir,
            cooldown_base=self.config.cooldown_base_sec,
        )
        self.claude_adapter = get_adapter("claude")
        self._ledger: Any | None = None
        self._ledger_lock = asyncio.Lock()
        self._hook_listener: HooksListener | None = None
        self._event_merger: EventMerger | None = None
        self._file_watcher: ClaudeSessionWatcher | None = None
        self._orchestrator: Orchestrator | None = None
        self._search_index: SearchIndex | None = None
        self._terminal_manager: TerminalManager | None = None
        self._sessions: dict[str, SessionRuntime] = {}
        self._background_tasks: set[asyncio.Task] = set()
        self._session_tasks: dict[str, set[asyncio.Task]] = {}

    async def initialize(self) -> None:
        self.account_manager.discover()
        await self.ledger()
        await self._ensure_event_pipeline()

    async def ledger(self) -> Any:
        if self._ledger is not None:
            return self._ledger
        async with self._ledger_lock:
            if self._ledger is None:
                db_path = get_default_config_path().with_name("triad.db")
                db_path.parent.mkdir(parents=True, exist_ok=True)
                allow_memory_ledger = os.environ.get("TRIAD_ALLOW_MEMORY_LEDGER") == "1"
                if CoreLedger is None and not allow_memory_ledger:
                    raise RuntimeError(
                        "aiosqlite is required for the desktop runtime; install project dependencies or set TRIAD_ALLOW_MEMORY_LEDGER=1 for test-only runs"
                    )
                ledger_cls = CoreLedger or MemoryLedger
                ledger = ledger_cls(db_path)
                await ledger.initialize()
                self._ledger = ledger
        assert self._ledger is not None
        return self._ledger

    async def shutdown(self) -> None:
        for runtime in list(self._sessions.values()):
            if runtime.pty is not None:
                with contextlib.suppress(Exception):
                    await runtime.pty.stop()
        self._sessions.clear()

        if self._hook_listener is not None:
            with contextlib.suppress(Exception):
                await self._hook_listener.stop()
            self._hook_listener = None

        if self._file_watcher is not None:
            with contextlib.suppress(Exception):
                await self._file_watcher.stop()
            self._file_watcher = None

        if self._terminal_manager is not None:
            with contextlib.suppress(Exception):
                await self._terminal_manager.close_all()
            self._terminal_manager = None

        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()
        self._session_tasks.clear()

        if self._ledger is not None:
            with contextlib.suppress(Exception):
                await self._ledger.close()
            self._ledger = None
        self._search_index = None

    async def open_project(self, path: str) -> dict[str, Any]:
        project_path = Path(path).expanduser().resolve()
        if not project_path.is_dir():
            raise ValueError(f"Not a directory: {path}")

        ledger = await self.ledger()
        await ledger.save_project(
            str(project_path), project_path.name, str(project_path)
        )
        return {
            "path": str(project_path),
            "name": project_path.name,
            "git_root": str(project_path),
        }

    async def list_projects(self) -> list[dict[str, Any]]:
        ledger = await self.ledger()
        rows = await ledger.list_projects()
        projects: list[dict[str, Any]] = []
        for row in rows:
            project_path = Path(str(row["path"])).expanduser().resolve()
            if not project_path.is_dir():
                continue
            projects.append(
                {
                    "path": str(project_path),
                    "name": row.get("name")
                    or row.get("display_name")
                    or project_path.name,
                    "git_root": str(Path(str(row["git_root"])).expanduser().resolve()),
                    "last_opened_at": self._format_ts(row.get("last_opened_at")),
                }
            )
        return projects

    async def create_session(
        self,
        project_path: str,
        mode: str,
        provider: str = "claude",
        title: str | None = None,
    ) -> dict[str, Any]:
        ledger = await self.ledger()
        normalized_project = str(Path(project_path).expanduser().resolve())
        session_title = title or f"New {mode} session"
        config_json = json.dumps(
            {
                "project_path": normalized_project,
                "provider": provider,
                "title": session_title,
            },
            ensure_ascii=False,
        )
        session_id = await ledger.create_session(
            mode=mode,
            task=session_title,
            config_json=config_json,
            title=session_title,
            project_path=normalized_project,
        )
        runtime = SessionRuntime(
            session_id=session_id,
            project_path=normalized_project,
            mode=mode,
            provider=provider,
            title=session_title,
        )
        self._sessions[session_id] = runtime
        await ledger.append_event(
            session_id,
            "session.created",
            {
                "project_path": normalized_project,
                "provider": provider,
                "mode": mode,
                "title": session_title,
            },
            provider=provider,
        )
        session_row = await ledger.get_session(session_id)
        return self._session_payload(runtime, session_row=session_row)

    async def list_sessions(
        self, project_path: str | None = None
    ) -> list[dict[str, Any]]:
        ledger = await self.ledger()
        target_project = (
            str(Path(project_path).expanduser().resolve()) if project_path else None
        )
        rows = await ledger.list_sessions(limit=1000, project_path=target_project)

        sessions: list[dict[str, Any]] = []
        for row in rows:
            config = self._load_config_json(row.get("config_json"))
            row_project = row.get("project_path") or config.get("project_path")
            sessions.append(
                {
                    "id": row["id"],
                    "project_path": row_project,
                    "title": row.get("title")
                    or row.get("task")
                    or config.get("title")
                    or "New session",
                    "mode": row.get("mode"),
                    "status": row.get("status"),
                    "created_at": self._format_ts(row.get("created_at")),
                    "updated_at": self._format_ts(row.get("updated_at")),
                    "message_count": await self._count_messages(row["id"]),
                    "provider": config.get("provider", "claude"),
                }
            )
        return sessions

    async def get_app_state(self) -> dict[str, Any]:
        projects = await self.list_projects()
        sessions = await self.list_sessions()
        last_project = projects[0]["path"] if projects else None
        preferred_session = (
            next(
                (
                    session
                    for session in sessions
                    if session["project_path"] == last_project
                ),
                None,
            )
            if last_project
            else None
        )
        last_session_id = (
            preferred_session or (sessions[0] if sessions else None) or {}
        ).get("id")
        return {
            "projects": projects,
            "sessions": sessions,
            "last_project": last_project,
            "last_session_id": last_session_id,
        }

    async def export_session(
        self,
        session_id: str,
        *,
        format_name: str = "archive",
        output_path: str | None = None,
    ) -> dict[str, Any]:
        ledger = await self.ledger()
        row = await ledger.get_session(session_id)
        if row is None:
            raise ValueError(f"Unknown session: {session_id}")

        runtime = self._sessions.get(session_id) or await self._hydrate_session(
            session_id
        )
        self._sessions[session_id] = runtime
        normalized_format = format_name.strip().lower() or "archive"
        target_path = self._resolve_export_path(
            runtime.title or row.get("title") or session_id,
            session_id,
            normalized_format,
            output_path,
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if normalized_format == "archive":
            archive = await self._build_session_archive(
                session_id,
                runtime=runtime,
                session_row=row,
            )
            target_path.write_text(
                json.dumps(archive, indent=2, ensure_ascii=False) + "\n"
            )
        elif normalized_format == "markdown":
            markdown = await self._render_session_markdown(
                session_id,
                runtime=runtime,
                session_row=row,
            )
            target_path.write_text(markdown, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported export format: {format_name}")

        return {
            "status": "ok",
            "session_id": session_id,
            "format": normalized_format,
            "path": str(target_path),
        }

    async def import_session(self, input_path: str) -> dict[str, Any]:
        source_path = Path(input_path).expanduser().resolve()
        if not source_path.is_file():
            raise ValueError(f"Import file not found: {input_path}")

        try:
            archive = json.loads(source_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid session archive: {exc}") from exc

        if archive.get("type") != "triad_desktop_session_archive":
            raise ValueError("Invalid session archive: unsupported type")
        if int(archive.get("version") or 0) != 1:
            raise ValueError("Invalid session archive: unsupported version")

        session_meta = archive.get("session")
        if not isinstance(session_meta, dict):
            raise ValueError("Invalid session archive: missing session payload")

        project_meta = (
            archive.get("project") if isinstance(archive.get("project"), dict) else {}
        )
        project_path = self._normalize_import_path(
            str(
                session_meta.get("project_path")
                or project_meta.get("path")
                or os.getcwd()
            )
        )
        project_name = str(
            project_meta.get("name") or Path(project_path).name or "Imported Project"
        )
        git_root = self._normalize_import_path(
            str(project_meta.get("git_root") or project_path)
        )

        provider = str(session_meta.get("provider") or "claude")
        mode = str(session_meta.get("mode") or "solo")
        title = str(
            session_meta.get("title") or session_meta.get("task") or source_path.stem
        )
        task = str(session_meta.get("task") or title)
        original_status = str(session_meta.get("status") or "completed")
        imported_status = (
            "paused" if original_status in {"active", "running"} else original_status
        )
        session_config = self._load_config_json(
            session_meta.get("config") or session_meta.get("config_json")
        )
        session_config.update(
            {
                "project_path": project_path,
                "provider": provider,
                "title": title,
                "imported_from_path": str(source_path),
                "imported_at": self._format_ts(time.time()),
                "imported_original_status": original_status,
                "imported_source_session_id": session_meta.get("source_session_id")
                or session_meta.get("id"),
            }
        )
        config_json = json.dumps(session_config, ensure_ascii=False)
        events = self._normalize_import_events(archive)

        ledger = await self.ledger()
        await ledger.save_project(project_path, project_name, git_root)
        imported_session_id = await ledger.create_session(
            mode=mode,
            task=task,
            config_json=config_json,
            title=title,
            project_path=project_path,
        )
        await self._restore_imported_events(imported_session_id, events)

        created_at = self._parse_ts(session_meta.get("created_at")) or time.time()
        updated_at = self._parse_ts(session_meta.get("updated_at"))
        if updated_at is None and events:
            updated_at = self._parse_ts(events[-1].get("ts")) or time.time()
        updated_at = updated_at or created_at
        await self._restore_imported_session_metadata(
            imported_session_id,
            mode=mode,
            task=task,
            title=title,
            project_path=project_path,
            status=imported_status,
            config_json=config_json,
            created_at=created_at,
            updated_at=updated_at,
        )

        runtime = SessionRuntime(
            session_id=imported_session_id,
            project_path=project_path,
            mode=mode,
            provider=provider,
            title=title,
            state=imported_status,
        )
        self._sessions[imported_session_id] = runtime
        hydrated = await self.get_session(imported_session_id)
        return {
            **hydrated,
            "project": {
                "path": project_path,
                "name": project_name,
                "git_root": git_root,
                "last_opened_at": self._format_ts(time.time()),
            },
            "path": str(source_path),
        }

    async def fork_session(
        self,
        source_session_id: str,
        *,
        title: str | None = None,
    ) -> dict[str, Any]:
        ledger = await self.ledger()
        source_row = await ledger.get_session(source_session_id)
        if source_row is None:
            raise ValueError(f"Unknown session: {source_session_id}")

        source_runtime = self._sessions.get(
            source_session_id
        ) or await self._hydrate_session(source_session_id)
        source_config = self._load_config_json(source_row.get("config_json"))
        source_title = str(
            source_row.get("title")
            or source_row.get("task")
            or source_runtime.title
            or "Session"
        )
        source_mode = str(source_row.get("mode") or source_runtime.mode or "solo")
        source_provider = str(
            source_config.get("provider") or source_runtime.provider or "claude"
        )
        source_project = str(
            Path(
                source_row.get("project_path")
                or source_config.get("project_path")
                or source_runtime.project_path
            )
            .expanduser()
            .resolve()
        )

        fork_title = title or self._derive_fork_title(source_title)
        fork_config = {
            **source_config,
            "project_path": source_project,
            "provider": source_provider,
            "title": fork_title,
            "fork_of_session_id": source_session_id,
            "fork_of_title": source_title,
            "forked_at": self._format_ts(time.time()),
        }
        fork_id = await ledger.create_session(
            mode=source_mode,
            task=fork_title,
            config_json=json.dumps(fork_config, ensure_ascii=False),
            title=fork_title,
            project_path=source_project,
        )
        fork_runtime = SessionRuntime(
            session_id=fork_id,
            project_path=source_project,
            mode=source_mode,
            provider=source_provider,
            title=fork_title,
        )
        self._sessions[fork_id] = fork_runtime

        await ledger.append_event(
            fork_id,
            "session.created",
            {
                "project_path": source_project,
                "provider": source_provider,
                "mode": source_mode,
                "title": fork_title,
                "fork_of_session_id": source_session_id,
            },
            provider=source_provider,
        )

        copied_events = await self._get_session_events(source_session_id, limit=4000)
        for event in copied_events:
            event_type = str(event.get("type", "")).strip()
            if event_type not in {
                "user.message",
                "message_finalized",
                "system",
                "tool_use",
                "tool_result",
                "review_finding",
                "run_failed",
            }:
                continue

            data = dict(event.get("data") or {})
            content = str(event.get("content") or "")
            if not data and content:
                data = (
                    {"error": content}
                    if event_type == "run_failed"
                    else {"content": content}
                )

            await ledger.append_event(
                fork_id,
                event_type,
                data,
                provider=str(event.get("provider")) if event.get("provider") else None,
                role=str(event.get("role")) if event.get("role") else None,
                agent=str(event.get("agent")) if event.get("agent") else None,
                content=content or None,
                artifact_id=str(event.get("artifact_id"))
                if event.get("artifact_id")
                else None,
            )

        fork_note = f'Continued from "{source_title}"'
        await ledger.append_event(
            fork_id,
            "system",
            {
                "content": fork_note,
                "source_session_id": source_session_id,
            },
            provider=source_provider,
            content=fork_note,
        )
        await ledger.update_session_status(fork_id, "active")
        session_row = await ledger.get_session(fork_id)
        return self._session_payload(fork_runtime, session_row=session_row)

    async def send_session_message(
        self,
        session_id: str,
        content: str,
        project_path: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        ledger = await self.ledger()
        runtime = self._sessions.get(session_id)
        if runtime is None:
            runtime = await self._hydrate_session(session_id, project_path=project_path)
            self._sessions[session_id] = runtime
        selected_provider = (provider or runtime.provider or "claude").strip()
        runtime.provider = selected_provider
        runtime.state = "running"
        has_live_context = selected_provider == "claude" and runtime.pty is not None

        await ledger.append_event(
            session_id,
            "user.message",
            {"content": content},
            provider=selected_provider,
            role="user",
            content=content,
        )

        existing = await ledger.get_session(session_id)
        existing_title = (existing or {}).get("title")
        if not existing_title:
            new_title = self._derive_title(content)
            await ledger.update_session_title(session_id, new_title)
            runtime.title = new_title

        effective_prompt = await self._build_contextual_prompt(
            session_id,
            content,
            provider=selected_provider,
            has_live_context=has_live_context,
        )

        if selected_provider == "claude":
            if self._file_watcher is not None:
                self._file_watcher.watch_session(
                    session_id,
                    runtime.project_path,
                    prompt_hint=content,
                )
            profile = self.account_manager.get_next("claude")
            env = None
            if profile is not None:
                env = self.claude_adapter.build_env(profile)

            claude = runtime.pty
            if claude is None:
                claude = ClaudePTY(
                    workdir=Path(runtime.project_path),
                    on_event=lambda event: self._handle_stream_event(session_id, event),
                    env=env,
                )
                runtime.pty = claude
                await claude.start()

            await claude.send(effective_prompt)
            return {"status": "sent", "session_id": session_id, "provider": "claude"}

        if runtime.pty is not None:
            with contextlib.suppress(Exception):
                await runtime.pty.stop()
            runtime.pty = None
        if self._file_watcher is not None:
            self._file_watcher.unwatch_session(session_id)

        task = asyncio.create_task(
            self._run_headless(
                session_id=session_id,
                prompt=effective_prompt,
                provider=selected_provider,
                model=model,
                workdir=Path(runtime.project_path),
            )
        )
        self._background_tasks.add(task)
        self._session_tasks.setdefault(session_id, set()).add(task)
        task.add_done_callback(
            lambda completed: self._discard_task(session_id, completed)
        )
        return {
            "status": "sent",
            "session_id": session_id,
            "provider": selected_provider,
        }

    async def stop_session(self, session_id: str) -> dict[str, Any]:
        runtime = self._sessions.get(session_id)
        if runtime and runtime.pty is not None:
            await runtime.pty.stop()
            runtime.pty = None
            runtime.state = "stopped"
        if self._file_watcher is not None:
            self._file_watcher.unwatch_session(session_id)
        for task in list(self._session_tasks.get(session_id, set())):
            task.cancel()
        ledger = await self.ledger()
        await ledger.update_session_status(session_id, "completed")
        return {"status": "stopped", "session_id": session_id}

    async def get_session(self, session_id: str) -> dict[str, Any]:
        ledger = await self.ledger()
        row = await ledger.get_session(session_id)
        if row is None:
            raise ValueError(f"Unknown session: {session_id}")
        runtime = self._sessions.get(session_id) or await self._hydrate_session(
            session_id
        )
        self._sessions[session_id] = runtime
        session_payload = self._session_payload(runtime, session_row=row)
        session_payload["message_count"] = await self._count_messages(session_id)
        return {
            "session": session_payload,
            "messages": await self._build_messages(session_id),
        }

    async def get_orchestrator(self) -> Orchestrator:
        if self._orchestrator is None:
            self._orchestrator = Orchestrator(
                on_event=self.emit_ui_event,
                account_manager=self.account_manager,
            )
        return self._orchestrator

    async def get_search_index(self) -> SearchIndex:
        if self._search_index is None:
            self._search_index = SearchIndex(self.config.db_path)
            await self._search_index.initialize()
        return self._search_index

    async def _prepare_mode_session(
        self,
        *,
        session_id: str,
        prompt: str,
        project_path: str | None = None,
        mode: str,
        provider: str,
    ) -> tuple[SessionRuntime, str]:
        ledger = await self.ledger()
        runtime = self._sessions.get(session_id)
        if runtime is None:
            runtime = await self._hydrate_session(session_id, project_path=project_path)
            self._sessions[session_id] = runtime
        if runtime.pty is not None:
            with contextlib.suppress(Exception):
                await runtime.pty.stop()
            runtime.pty = None
        if self._file_watcher is not None:
            self._file_watcher.unwatch_session(session_id)
        runtime.provider = provider
        runtime.mode = mode
        runtime.state = "running"

        await ledger.append_event(
            session_id,
            "user.message",
            {"content": prompt},
            provider=provider,
            role="user",
            content=prompt,
        )

        existing = await ledger.get_session(session_id)
        existing_title = (existing or {}).get("title")
        if not existing_title:
            new_title = self._derive_title(prompt)
            await ledger.update_session_title(session_id, new_title)
            runtime.title = new_title

        await ledger.update_session_status(session_id, "running")
        effective_prompt = await self._build_contextual_prompt(
            session_id,
            prompt,
            provider=provider,
            has_live_context=False,
        )
        return runtime, effective_prompt

    async def start_critic_session(
        self,
        *,
        session_id: str,
        prompt: str,
        project_path: str | None = None,
        writer_provider: str | None = None,
        critic_provider: str | None = None,
        max_rounds: int = 3,
        model: str | None = None,
    ) -> dict[str, Any]:
        selected_writer = (writer_provider or "claude").strip() or "claude"
        runtime, effective_prompt = await self._prepare_mode_session(
            session_id=session_id,
            prompt=prompt,
            project_path=project_path,
            mode="critic",
            provider=selected_writer,
        )
        selected_critic = (
            critic_provider or self._default_critic_provider(selected_writer)
        ).strip()

        async def run() -> None:
            orchestrator = await self.get_orchestrator()
            await orchestrator.run_critic(
                session_id=session_id,
                prompt=effective_prompt,
                workdir=Path(runtime.project_path),
                writer_provider=selected_writer,
                critic_provider=selected_critic,
                max_rounds=max_rounds,
                writer_model=model,
            )

        task = asyncio.create_task(run())
        self._background_tasks.add(task)
        self._session_tasks.setdefault(session_id, set()).add(task)
        task.add_done_callback(
            lambda completed: self._discard_task(session_id, completed)
        )
        return {
            "status": "started",
            "session_id": session_id,
            "writer_provider": selected_writer,
            "critic_provider": selected_critic,
        }

    async def start_brainstorm_session(
        self,
        *,
        session_id: str,
        prompt: str,
        project_path: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        primary_provider = (provider or "claude").strip() or "claude"
        runtime, effective_prompt = await self._prepare_mode_session(
            session_id=session_id,
            prompt=prompt,
            project_path=project_path,
            mode="brainstorm",
            provider=primary_provider,
        )
        orchestrator = await self.get_orchestrator()
        ideators, moderator = orchestrator.default_brainstorm_providers(
            primary_provider
        )

        async def run() -> None:
            await orchestrator.run_brainstorm(
                session_id=session_id,
                prompt=effective_prompt,
                workdir=Path(runtime.project_path),
                ideator_providers=ideators,
                moderator_provider=moderator,
                ideator_model=model,
                moderator_model=model if moderator == primary_provider else None,
            )

        task = asyncio.create_task(run())
        self._background_tasks.add(task)
        self._session_tasks.setdefault(session_id, set()).add(task)
        task.add_done_callback(
            lambda completed: self._discard_task(session_id, completed)
        )
        return {
            "status": "started",
            "session_id": session_id,
            "ideator_providers": ideators,
            "moderator_provider": moderator,
        }

    async def start_delegate_session(
        self,
        *,
        session_id: str,
        prompt: str,
        project_path: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        primary_provider = (provider or "claude").strip() or "claude"
        runtime, effective_prompt = await self._prepare_mode_session(
            session_id=session_id,
            prompt=prompt,
            project_path=project_path,
            mode="delegate",
            provider=primary_provider,
        )
        orchestrator = await self.get_orchestrator()
        providers = orchestrator.default_delegate_providers(primary_provider)

        async def run() -> None:
            await orchestrator.run_delegate(
                session_id=session_id,
                prompt=effective_prompt,
                workdir=Path(runtime.project_path),
                lane_providers=providers,
                model=model,
            )

        task = asyncio.create_task(run())
        self._background_tasks.add(task)
        self._session_tasks.setdefault(session_id, set()).add(task)
        task.add_done_callback(
            lambda completed: self._discard_task(session_id, completed)
        )
        return {
            "status": "started",
            "session_id": session_id,
            "providers": providers,
        }

    async def _ensure_event_pipeline(self) -> None:
        if self._event_merger is not None:
            return

        async def forward_to_ui(event: dict[str, Any]) -> None:
            await self.emit_ui_event(event)

        self._event_merger = EventMerger(on_ui_event=forward_to_ui)
        self._hook_listener = HooksListener(on_event=self._event_merger.handle)
        await self._hook_listener.start()
        self._file_watcher = ClaudeSessionWatcher(on_event=self._event_merger.handle)
        await self._file_watcher.start()

    async def _handle_stream_event(
        self, session_id: str, event: dict[str, Any]
    ) -> None:
        normalized = dict(event)
        normalized.setdefault("session_id", session_id)
        if self._event_merger is None:
            await self._ensure_event_pipeline()
        assert self._event_merger is not None
        await self._event_merger.handle(normalized)

    async def _run_headless(
        self,
        *,
        session_id: str,
        prompt: str,
        provider: str,
        model: str | None,
        workdir: Path,
    ) -> None:
        adapter = get_adapter(provider)
        profile = self.account_manager.get_next(provider)
        if profile is None:
            await self.emit_ui_event(
                {
                    "session_id": session_id,
                    "type": "run_failed",
                    "provider": provider,
                    "error": f"No available {provider} accounts",
                }
            )
            return

        chunks: list[str] = []
        errors: list[str] = []
        returncode: int | None = None
        try:
            async for event in adapter.execute_stream(
                profile=profile,
                prompt=prompt,
                workdir=workdir,
                model=model,
            ):
                if event.kind == "text" and event.text:
                    chunks.append(event.text)
                    await self.emit_ui_event(
                        {
                            "session_id": session_id,
                            "type": "text_delta",
                            "provider": provider,
                            "delta": event.text,
                        }
                    )
                elif event.kind == "tool_use":
                    payload = event.data or {}
                    await self.emit_ui_event(
                        {
                            "session_id": session_id,
                            "type": "tool_use",
                            "provider": provider,
                            **payload,
                        }
                    )
                elif event.kind == "tool_result":
                    payload = event.data or {}
                    await self.emit_ui_event(
                        {
                            "session_id": session_id,
                            "type": "tool_result",
                            "provider": provider,
                            **payload,
                        }
                    )
                elif event.kind == "error" and event.text:
                    errors.append(event.text)
                    await self.emit_ui_event(
                        {
                            "session_id": session_id,
                            "type": "stderr",
                            "provider": provider,
                            "data": event.text,
                        }
                    )
                elif event.kind == "done":
                    payload = event.data or {}
                    raw_returncode = payload.get("returncode")
                    if isinstance(raw_returncode, int):
                        returncode = raw_returncode

            combined_error = "\n".join(part for part in errors if part).strip()
            if combined_error or returncode not in (None, 0):
                error_text = (
                    combined_error or f"{provider} exited with code {returncode}"
                )
                if is_rate_limited(error_text):
                    self.account_manager.mark_rate_limited(provider, profile.name)
                await self.emit_ui_event(
                    {
                        "session_id": session_id,
                        "type": "run_failed",
                        "provider": provider,
                        "error": error_text,
                    }
                )
                return

            self.account_manager.mark_success(provider, profile.name)
            final_text = "\n".join(part for part in chunks if part).strip()
            if final_text:
                await self.emit_ui_event(
                    {
                        "session_id": session_id,
                        "type": "message_finalized",
                        "provider": provider,
                        "content": final_text,
                    }
                )
            await self.emit_ui_event(
                {
                    "session_id": session_id,
                    "type": "run_completed",
                    "provider": provider,
                }
            )
        except asyncio.CancelledError:
            await self.emit_ui_event(
                {
                    "session_id": session_id,
                    "type": "run_failed",
                    "provider": provider,
                    "error": "Run cancelled",
                }
            )
        except Exception as exc:
            await self.emit_ui_event(
                {
                    "session_id": session_id,
                    "type": "run_failed",
                    "provider": provider,
                    "error": str(exc),
                }
            )

    async def get_terminal_manager(self) -> TerminalManager:
        if self._terminal_manager is None:

            async def on_output(terminal_id: str, data: bytes) -> None:
                await self.emit_ui_event(
                    {
                        "session_id": "__terminal__",
                        "type": "terminal_output",
                        "terminal_id": terminal_id,
                        "data": base64.b64encode(data).decode("ascii"),
                    }
                )

            self._terminal_manager = TerminalManager(on_output=on_output)
        return self._terminal_manager

    async def _hydrate_session(
        self,
        session_id: str,
        project_path: str | None = None,
    ) -> SessionRuntime:
        ledger = await self.ledger()
        row = await ledger.get_session(session_id)
        if row is None:
            if project_path is None:
                raise ValueError(f"Unknown session: {session_id}")
            return SessionRuntime(
                session_id=session_id,
                project_path=str(Path(project_path).expanduser().resolve()),
                mode="solo",
                provider="claude",
                title="Recovered session",
            )

        config = self._load_config_json(row.get("config_json"))
        resolved_project = str(
            Path(project_path or config.get("project_path") or os.getcwd())
            .expanduser()
            .resolve()
        )
        return SessionRuntime(
            session_id=session_id,
            project_path=resolved_project,
            mode=str(row.get("mode") or "solo"),
            provider=str(config.get("provider") or "claude"),
            title=str(
                row.get("title")
                or row.get("task")
                or config.get("title")
                or "Recovered session"
            ),
        )

    async def _count_events(self, session_id: str) -> int:
        ledger = await self.ledger()
        count_events = getattr(ledger, "count_events", None)
        if callable(count_events):
            return int(await count_events(session_id))
        db = getattr(ledger, "_db", None)
        if db is None:
            return 0
        rows = await db.execute_fetchall(
            "SELECT COUNT(*) AS count FROM events WHERE session_id = ?",
            (session_id,),
        )
        return int(rows[0]["count"]) if rows else 0

    async def _count_messages(self, session_id: str) -> int:
        events = await self._get_session_events(session_id, limit=2000)
        if events:
            finalized_ids: set[str] = set()
            count = 0
            for event in events:
                if event.get("type") == "user.message":
                    count += 1
                    continue
                if event.get("type") != "message_finalized":
                    continue
                data = event.get("data") or {}
                message_id = str(data.get("message_id") or event.get("id"))
                if message_id in finalized_ids:
                    continue
                finalized_ids.add(message_id)
                count += 1
            return count
        return await self._count_events(session_id)

    async def _build_messages(self, session_id: str) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        events = await self._get_session_events(session_id, limit=2000)
        assistant_indexes: dict[str, int] = {}
        for event in events:
            event_type = str(event.get("type", ""))
            data = event.get("data") or {}
            timestamp = self._format_ts(event.get("ts") or event.get("timestamp"))
            provider = event.get("provider")
            if event_type == "user.message":
                content = str(data.get("content") or event.get("content") or "")
                if content:
                    messages.append(
                        {
                            "id": f"msg_user_{event['id']}",
                            "session_id": session_id,
                            "role": "user",
                            "content": content,
                            "provider": provider,
                            "timestamp": timestamp,
                        }
                    )
            elif event_type == "message_finalized":
                content = str(data.get("content") or event.get("content") or "")
                if content:
                    message_key = str(data.get("message_id") or event.get("id"))
                    message = {
                        "id": f"msg_assistant_{message_key}",
                        "session_id": session_id,
                        "role": "assistant",
                        "content": content,
                        "provider": provider,
                        "agent_role": event.get("role"),
                        "timestamp": timestamp,
                    }
                    existing_index = assistant_indexes.get(message_key)
                    if existing_index is None:
                        assistant_indexes[message_key] = len(messages)
                        messages.append(message)
                    else:
                        messages[existing_index] = message
            elif event_type == "system":
                content = str(data.get("content") or event.get("content") or "")
                if content:
                    messages.append(
                        {
                            "id": f"msg_system_{event['id']}",
                            "session_id": session_id,
                            "role": "system",
                            "content": content,
                            "provider": provider,
                            "timestamp": timestamp,
                        }
                    )
            elif event_type == "diff_snapshot":
                messages.append(
                    {
                        "id": f"msg_diff_{event['id']}",
                        "session_id": session_id,
                        "role": "system",
                        "content": str(data.get("path") or "Diff snapshot"),
                        "provider": provider,
                        "timestamp": timestamp,
                        "event_type": "diff_snapshot",
                        "diff_snapshot": {
                            "path": str(data.get("path") or ""),
                            "old_text": str(data.get("old_text") or ""),
                            "new_text": str(data.get("new_text") or ""),
                        },
                    }
                )
            elif event_type == "tool_use":
                tool_name = str(data.get("tool") or "tool")
                tool_input = data.get("input") or {}
                tool_input_map = tool_input if isinstance(tool_input, dict) else {}
                diff_snapshot = None
                if tool_name in {"Edit", "Write"}:
                    old_text = str(
                        data.get("old_text")
                        or data.get("old_string")
                        or tool_input_map.get("old_text")
                        or tool_input_map.get("old_string")
                        or ""
                    )
                    new_text = str(
                        data.get("new_text")
                        or data.get("new_string")
                        or tool_input_map.get("new_text")
                        or tool_input_map.get("new_string")
                        or tool_input_map.get("content")
                        or data.get("content")
                        or ""
                    )
                    path = str(
                        data.get("path")
                        or data.get("file_path")
                        or tool_input_map.get("target_file")
                        or tool_input_map.get("path")
                        or tool_input_map.get("file_path")
                        or ""
                    )
                    if path and (old_text or new_text):
                        diff_snapshot = {
                            "path": path,
                            "old_text": old_text,
                            "new_text": new_text,
                        }
                messages.append(
                    {
                        "id": f"msg_tool_{event['id']}",
                        "session_id": session_id,
                        "role": "system",
                        "content": str(data.get("content") or tool_name),
                        "provider": provider,
                        "timestamp": timestamp,
                        "event_type": "tool_use",
                        "tool_event": {
                            "tool": tool_name,
                            "input": tool_input,
                            "output": data.get("output"),
                            "status": str(data.get("status") or "running"),
                        },
                        "diff_snapshot": diff_snapshot,
                    }
                )
            elif event_type == "tool_result":
                tool_name = str(data.get("tool") or "tool")
                tool_input = data.get("input") or {}
                tool_input_map = tool_input if isinstance(tool_input, dict) else {}
                diff_snapshot = None
                if tool_name in {"Edit", "Write"}:
                    old_text = str(
                        data.get("old_text")
                        or data.get("old_string")
                        or tool_input_map.get("old_text")
                        or tool_input_map.get("old_string")
                        or ""
                    )
                    new_text = str(
                        data.get("new_text")
                        or data.get("new_string")
                        or tool_input_map.get("new_text")
                        or tool_input_map.get("new_string")
                        or tool_input_map.get("content")
                        or data.get("content")
                        or ""
                    )
                    path = str(
                        data.get("path")
                        or data.get("file_path")
                        or tool_input_map.get("target_file")
                        or tool_input_map.get("path")
                        or tool_input_map.get("file_path")
                        or ""
                    )
                    if path and (old_text or new_text):
                        diff_snapshot = {
                            "path": path,
                            "old_text": old_text,
                            "new_text": new_text,
                        }
                messages.append(
                    {
                        "id": f"msg_tool_result_{event['id']}",
                        "session_id": session_id,
                        "role": "system",
                        "content": str(data.get("content") or tool_name),
                        "provider": provider,
                        "timestamp": timestamp,
                        "event_type": "tool_result",
                        "tool_event": {
                            "tool": tool_name,
                            "input": tool_input,
                            "output": data.get("output"),
                            "status": str(
                                data.get("status")
                                or (
                                    "failed"
                                    if data.get("success") is False
                                    else "completed"
                                )
                            ),
                        },
                        "diff_snapshot": diff_snapshot,
                    }
                )
            elif event_type == "review_finding":
                messages.append(
                    {
                        "id": f"msg_finding_{event['id']}",
                        "session_id": session_id,
                        "role": "system",
                        "content": str(data.get("title") or "Finding"),
                        "provider": provider,
                        "timestamp": timestamp,
                        "event_type": "review_finding",
                        "review_finding": {
                            "severity": str(data.get("severity") or "P2"),
                            "file": str(data.get("file") or ""),
                            "line": data.get("line"),
                            "line_range": str(data.get("line_range") or "") or None,
                            "title": str(data.get("title") or "Finding"),
                            "explanation": str(
                                data.get("explanation") or "Potential issue detected."
                            ),
                        },
                    }
                )
            elif event_type == "run_failed":
                messages.append(
                    {
                        "id": f"msg_error_{event['id']}",
                        "session_id": session_id,
                        "role": "system",
                        "content": str(
                            data.get("error") or event.get("content") or "Run failed"
                        ),
                        "provider": provider,
                        "timestamp": timestamp,
                        "event_type": "run_failed",
                    }
                )
            elif event_type == "stderr":
                content = str(data.get("data") or event.get("content") or "")
                if content:
                    messages.append(
                        {
                            "id": f"msg_stderr_{event['id']}",
                            "session_id": session_id,
                            "role": "system",
                            "content": content,
                            "provider": provider,
                            "timestamp": timestamp,
                            "event_type": "stderr",
                        }
                    )
        return messages

    async def _get_session_events(
        self, session_id: str, limit: int = 500
    ) -> list[dict[str, Any]]:
        ledger = await self.ledger()
        get_session_events = getattr(ledger, "get_session_events", None)
        if not callable(get_session_events):
            return []
        return list(await get_session_events(session_id, limit))

    async def _build_contextual_prompt(
        self,
        session_id: str,
        latest_user_content: str,
        *,
        provider: str,
        has_live_context: bool,
    ) -> str:
        if has_live_context:
            return latest_user_content

        messages = await self._build_messages(session_id)
        history = [
            message
            for message in messages
            if message.get("role") in {"user", "assistant"}
        ]
        if history and history[-1].get("role") == "user":
            last_content = str(history[-1].get("content") or "").strip()
            if last_content == latest_user_content.strip():
                history = history[:-1]
        if not history:
            return latest_user_content

        transcript_lines: list[str] = []
        budget = 12000
        used = 0
        for message in reversed(history[-24:]):
            content = " ".join(str(message.get("content") or "").split())
            if not content:
                continue
            if len(content) > 1600:
                content = content[:1600].rstrip() + "..."
            prefix = "User" if message.get("role") == "user" else "Assistant"
            line = f"{prefix}: {content}"
            if transcript_lines and used + len(line) > budget:
                break
            transcript_lines.append(line)
            used += len(line)
        transcript_lines.reverse()
        if not transcript_lines:
            return latest_user_content

        return (
            "You are continuing an existing Triad desktop session.\n"
            f"The active provider is {provider}. Use the conversation history as context, "
            "then respond naturally to the latest user message.\n"
            "Do not restate the full history unless it is necessary.\n\n"
            "Conversation so far:\n"
            + "\n\n".join(transcript_lines)
            + "\n\nLatest user message:\n"
            + latest_user_content
        )

    async def _build_session_archive(
        self,
        session_id: str,
        *,
        runtime: SessionRuntime,
        session_row: dict[str, Any],
    ) -> dict[str, Any]:
        config = self._load_config_json(session_row.get("config_json"))
        project_path = str(
            session_row.get("project_path")
            or config.get("project_path")
            or runtime.project_path
        )
        session_payload = self._session_payload(runtime, session_row=session_row)
        session_payload["message_count"] = await self._count_messages(session_id)
        session_payload["source_session_id"] = session_id
        session_payload["task"] = str(session_row.get("task") or runtime.title)
        session_payload["config"] = config
        return {
            "type": "triad_desktop_session_archive",
            "version": 1,
            "exported_at": self._format_ts(time.time()),
            "session": session_payload,
            "project": {
                "path": project_path,
                "name": Path(project_path).name or "Project",
                "git_root": project_path,
            },
            "messages": await self._build_messages(session_id),
            "events": await self._get_session_events(session_id, limit=5000),
        }

    async def _render_session_markdown(
        self,
        session_id: str,
        *,
        runtime: SessionRuntime,
        session_row: dict[str, Any],
    ) -> str:
        archive = await self._build_session_archive(
            session_id,
            runtime=runtime,
            session_row=session_row,
        )
        session_data = archive["session"]
        messages = archive["messages"]
        lines = [
            f"# {session_data.get('title') or 'Session Export'}",
            "",
            f"- Session ID: {session_id}",
            f"- Mode: {session_data.get('mode') or 'solo'}",
            f"- Provider: {session_data.get('provider') or 'claude'}",
            f"- Status: {session_data.get('status') or 'completed'}",
            f"- Project: {session_data.get('project_path') or runtime.project_path}",
            f"- Exported At: {archive.get('exported_at') or self._format_ts(time.time())}",
            "",
            "## Transcript",
            "",
        ]

        if not messages:
            lines.append("_No transcript messages were recorded for this session._")
            return "\n".join(lines) + "\n"

        for message in messages:
            role = str(message.get("role") or "system").capitalize()
            provider = str(message.get("provider") or "").strip()
            agent_role = str(message.get("agent_role") or "").strip()
            badges = [badge for badge in (provider, agent_role) if badge]
            heading = role if not badges else f"{role} ({', '.join(badges)})"
            lines.extend(
                [
                    f"### {heading}",
                    "",
                    str(message.get("content") or "").rstrip() or "_Empty message_",
                    "",
                ]
            )

        return "\n".join(lines) + "\n"

    def _session_payload(
        self,
        runtime: SessionRuntime,
        session_row: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": runtime.session_id,
            "project_path": runtime.project_path,
            "title": runtime.title,
            "mode": runtime.mode,
            "status": str((session_row or {}).get("status") or runtime.state),
            "created_at": self._format_ts((session_row or {}).get("created_at")),
            "updated_at": self._format_ts((session_row or {}).get("updated_at")),
            "message_count": 0,
            "provider": runtime.provider,
        }

    async def _restore_imported_events(
        self,
        session_id: str,
        events: list[dict[str, Any]],
    ) -> None:
        if not events:
            return

        ledger = await self.ledger()
        normalized_events = sorted(
            events, key=lambda event: int(event.get("seq", 0) or 0)
        )
        if isinstance(ledger, MemoryLedger):
            next_event_id = len(ledger._events) + 1
            last_ts: float | None = None
            for index, event in enumerate(normalized_events, start=1):
                ts = self._parse_ts(event.get("ts")) or time.time()
                last_ts = ts
                ledger._events.append(
                    {
                        "id": next_event_id,
                        "session_id": session_id,
                        "seq": index,
                        "event_type": str(event.get("type") or "system"),
                        "agent": str(event.get("agent"))
                        if event.get("agent")
                        else None,
                        "content": str(event.get("content"))
                        if event.get("content") is not None
                        else None,
                        "artifact_id": str(event.get("artifact_id"))
                        if event.get("artifact_id")
                        else None,
                        "run_id": str(event.get("run_id"))
                        if event.get("run_id")
                        else None,
                        "provider": str(event.get("provider"))
                        if event.get("provider")
                        else None,
                        "role": str(event.get("role")) if event.get("role") else None,
                        "data_json": json.dumps(
                            event.get("data") or {}, ensure_ascii=False
                        ),
                        "timestamp": str(event.get("timestamp") or self._format_ts(ts)),
                        "ts": ts,
                    }
                )
                next_event_id += 1
            ledger._seq[session_id] = len(normalized_events)
            if session_id in ledger._sessions and last_ts is not None:
                ledger._sessions[session_id]["updated_at"] = last_ts
            return

        db = getattr(ledger, "_db", None)
        if db is None:
            for event in normalized_events:
                await ledger.append_event(
                    session_id,
                    str(event.get("type") or "system"),
                    dict(event.get("data") or {}),
                    provider=str(event.get("provider"))
                    if event.get("provider")
                    else None,
                    role=str(event.get("role")) if event.get("role") else None,
                    run_id=str(event.get("run_id")) if event.get("run_id") else None,
                    agent=str(event.get("agent")) if event.get("agent") else None,
                    content=str(event.get("content"))
                    if event.get("content") is not None
                    else None,
                    artifact_id=str(event.get("artifact_id"))
                    if event.get("artifact_id")
                    else None,
                )
            return

        for index, event in enumerate(normalized_events, start=1):
            ts = self._parse_ts(event.get("ts")) or time.time()
            await db.execute(
                """
                INSERT INTO events (
                    session_id,
                    seq,
                    event_type,
                    agent,
                    content,
                    artifact_id,
                    run_id,
                    provider,
                    role,
                    data_json,
                    timestamp,
                    ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    index,
                    str(event.get("type") or "system"),
                    str(event.get("agent")) if event.get("agent") else None,
                    str(event.get("content"))
                    if event.get("content") is not None
                    else None,
                    str(event.get("artifact_id")) if event.get("artifact_id") else None,
                    str(event.get("run_id")) if event.get("run_id") else None,
                    str(event.get("provider")) if event.get("provider") else None,
                    str(event.get("role")) if event.get("role") else None,
                    json.dumps(event.get("data") or {}, ensure_ascii=False),
                    str(event.get("timestamp") or self._format_ts(ts)),
                    ts,
                ),
            )
        await db.commit()

    async def _restore_imported_session_metadata(
        self,
        session_id: str,
        *,
        mode: str,
        task: str,
        title: str,
        project_path: str,
        status: str,
        config_json: str,
        created_at: float,
        updated_at: float,
    ) -> None:
        ledger = await self.ledger()
        if isinstance(ledger, MemoryLedger):
            row = ledger._sessions.get(session_id)
            if row is None:
                return
            row.update(
                {
                    "mode": mode,
                    "task": task,
                    "title": title,
                    "project_path": project_path,
                    "status": status,
                    "config_json": config_json,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )
            return

        db = getattr(ledger, "_db", None)
        if db is None:
            await ledger.update_session_title(session_id, title)
            await ledger.update_session_status(session_id, status)
            return

        await db.execute(
            """
            UPDATE sessions
            SET mode = ?, task = ?, title = ?, project_path = ?, status = ?,
                config_json = ?, created_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                mode,
                task,
                title,
                project_path,
                status,
                config_json,
                created_at,
                updated_at,
                session_id,
            ),
        )
        await db.commit()

    async def _persist_ui_event(self, event: dict[str, Any]) -> None:
        normalized_event = normalize_stream_event(event)
        session_id = str(normalized_event.get("session_id", "")).strip()
        if not session_id or session_id == "__terminal__":
            return
        ledger = await self.ledger()
        event_type = str(normalized_event.get("type", "system"))
        provider = normalized_event.get("provider")
        role = normalized_event.get("role")
        runtime = self._sessions.get(session_id)
        await ledger.append_event(
            session_id,
            event_type,
            normalized_event,
            provider=str(provider) if provider else None,
            role=str(role) if role else None,
            run_id=str(normalized_event.get("run_id"))
            if normalized_event.get("run_id")
            else None,
            agent=str(provider) if provider else None,
            content=str(
                normalized_event.get("content")
                or normalized_event.get("delta")
                or normalized_event.get("data")
                or ""
            ),
        )
        if runtime is not None and provider:
            runtime.provider = str(provider)
        if runtime is not None and event_type == "text_delta":
            runtime.state = "running"
        if event_type in {
            "message_finalized",
            "tool_use",
            "tool_result",
            "review_finding",
            "system",
        }:
            if (
                event_type == "message_finalized"
                and normalized_event.get("authoritative")
                and runtime is not None
                and runtime.state in {"completed", "failed"}
            ):
                await ledger.update_session_status(session_id, runtime.state)
            else:
                await ledger.update_session_status(session_id, "running")
                if runtime is not None:
                    runtime.state = "running"
        elif event_type == "run_completed":
            await ledger.update_session_status(session_id, "completed")
            if runtime is not None:
                runtime.state = "completed"
        elif event_type == "run_failed":
            await ledger.update_session_status(session_id, "failed")
            if runtime is not None:
                runtime.state = "failed"

    async def emit_ui_event(self, event: dict[str, Any]) -> None:
        normalized_event = normalize_stream_event(event)
        await self._persist_ui_event(normalized_event)
        await bridge.notify("event.stream", normalized_event)

    async def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        normalized = query.strip()
        if not normalized:
            return []

        ledger = await self.ledger()
        if isinstance(ledger, MemoryLedger):
            return self._search_memory(ledger, normalized, limit)

        search_index = await self.get_search_index()
        return await search_index.search(normalized, limit)

    async def get_diagnostics(self) -> dict[str, Any]:
        active_terminals: list[str] = []
        if self._terminal_manager is not None:
            with contextlib.suppress(Exception):
                active = self._terminal_manager.list_active()
                active_terminals = (
                    await active if inspect.isawaitable(active) else active
                )

        return {
            "version": "0.1.0",
            "python_version": sys.version,
            "triad_home": str(self.config.triad_home),
            "db_path": str(self.config.db_path),
            "providers": {
                provider: self.account_manager.pool_status(provider)
                for provider in ("claude", "codex", "gemini")
            },
            "active_claude_sessions": [
                session_id
                for session_id, runtime in self._sessions.items()
                if runtime.pty is not None
            ],
            "active_sessions": [
                {
                    "id": runtime.session_id,
                    "mode": runtime.mode,
                    "provider": runtime.provider,
                    "project_path": runtime.project_path,
                    "state": runtime.state,
                }
                for runtime in self._sessions.values()
            ],
            "active_terminals": active_terminals,
            "active_file_watches": self._file_watcher.snapshot()
            if self._file_watcher is not None
            else [],
            "hooks_socket": str(
                self._hook_listener.socket_path
                if self._hook_listener
                else default_socket_path()
            ),
        }

    @staticmethod
    def _load_config_json(raw: Any) -> dict[str, Any]:
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _derive_title(content: str) -> str:
        title = " ".join(content.strip().split())
        if not title:
            return "New session"
        return title[:60]

    @staticmethod
    def _derive_fork_title(source_title: str) -> str:
        title = " ".join(source_title.strip().split()) or "Session"
        if title.lower().endswith("(fork)"):
            return title[:60]
        return f"{title[:52]} (fork)"

    def _discard_task(self, session_id: str, task: asyncio.Task) -> None:
        self._background_tasks.discard(task)
        tasks = self._session_tasks.get(session_id)
        if tasks is None:
            return
        tasks.discard(task)
        if not tasks:
            self._session_tasks.pop(session_id, None)

    @staticmethod
    def _format_ts(value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, str):
            return value
        try:
            return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(float(value)))
        except (TypeError, ValueError):
            return str(value)

    def _default_critic_provider(self, writer_provider: str) -> str:
        candidates = [
            provider
            for provider in ("codex", "claude", "gemini")
            if provider != writer_provider
        ]
        for provider in candidates:
            if self.account_manager.pools.get(provider):
                return provider
        return candidates[0] if candidates else writer_provider

    @staticmethod
    def _search_memory(
        ledger: MemoryLedger,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        needle = query.casefold()
        results: list[dict[str, Any]] = []
        for event in reversed(ledger._events):
            content = str(event.get("content") or "")
            if not content:
                continue
            index = content.casefold().find(needle)
            if index < 0:
                continue
            session = ledger._sessions.get(str(event.get("session_id")), {})
            snippet = DesktopRuntime._highlight_snippet(content, index, len(query))
            results.append(
                {
                    "event_id": int(event["id"]),
                    "session_id": str(event["session_id"]),
                    "session_title": str(
                        session.get("title") or session.get("task") or "Session"
                    ),
                    "project_path": str(session.get("project_path") or ""),
                    "snippet": snippet,
                }
            )
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _highlight_snippet(content: str, start: int, length: int) -> str:
        prefix_start = max(0, start - 48)
        suffix_end = min(len(content), start + length + 72)
        prefix = content[prefix_start:start]
        match = content[start : start + length]
        suffix = content[start + length : suffix_end]
        head = "..." if prefix_start > 0 else ""
        tail = "..." if suffix_end < len(content) else ""
        return f"{head}{prefix}<mark>{match}</mark>{suffix}{tail}"

    def _resolve_export_path(
        self,
        title: str,
        session_id: str,
        format_name: str,
        output_path: str | None,
    ) -> Path:
        if output_path:
            return Path(output_path).expanduser().resolve()

        suffix = "json" if format_name == "archive" else "md"
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        slug = self._slugify(title) or session_id
        filename = f"{stamp}-{slug}-{session_id}.{suffix}"
        return (self.config.exports_dir / filename).resolve()

    @staticmethod
    def _normalize_import_events(archive: dict[str, Any]) -> list[dict[str, Any]]:
        raw_events = archive.get("events")
        if isinstance(raw_events, list) and raw_events:
            normalized: list[dict[str, Any]] = []
            for index, item in enumerate(raw_events, start=1):
                if not isinstance(item, dict):
                    continue
                event_type = str(item.get("type") or "system")
                if event_type == "user.message":
                    data = (
                        item.get("data") if isinstance(item.get("data"), dict) else {}
                    )
                    normalized.append(
                        {
                            "seq": int(item.get("seq") or index),
                            "type": event_type,
                            "provider": str(item.get("provider"))
                            if item.get("provider")
                            else None,
                            "role": str(item.get("role")) if item.get("role") else None,
                            "agent": str(item.get("agent"))
                            if item.get("agent")
                            else None,
                            "run_id": str(item.get("run_id"))
                            if item.get("run_id")
                            else None,
                            "content": str(item.get("content"))
                            if item.get("content") is not None
                            else None,
                            "artifact_id": str(item.get("artifact_id"))
                            if item.get("artifact_id")
                            else None,
                            "timestamp": item.get("timestamp"),
                            "ts": item.get("ts"),
                            "data": data,
                        }
                    )
                    continue

                if canonical_event_type(event_type) not in CANONICAL_STREAM_EVENT_TYPES:
                    data = (
                        item.get("data") if isinstance(item.get("data"), dict) else {}
                    )
                    normalized.append(
                        {
                            "seq": int(item.get("seq") or index),
                            "type": event_type,
                            "provider": str(item.get("provider"))
                            if item.get("provider")
                            else None,
                            "role": str(item.get("role")) if item.get("role") else None,
                            "agent": str(item.get("agent"))
                            if item.get("agent")
                            else None,
                            "run_id": str(item.get("run_id"))
                            if item.get("run_id")
                            else None,
                            "content": str(item.get("content"))
                            if item.get("content") is not None
                            else None,
                            "artifact_id": str(item.get("artifact_id"))
                            if item.get("artifact_id")
                            else None,
                            "timestamp": item.get("timestamp"),
                            "ts": item.get("ts"),
                            "data": data,
                        }
                    )
                    continue

                normalized_event = normalize_stream_event(
                    {
                        **(
                            item.get("data")
                            if isinstance(item.get("data"), dict)
                            else {}
                        ),
                        **item,
                        "session_id": str(item.get("session_id") or "imported-session"),
                        "type": event_type,
                        "provider": item.get("provider"),
                        "role": item.get("role"),
                        "timestamp": item.get("timestamp"),
                        "message_id": item.get("message_id")
                        or (item.get("data") or {}).get("message_id")
                        if isinstance(item.get("data"), dict)
                        else item.get("message_id"),
                    }
                )
                normalized.append(
                    {
                        "seq": int(item.get("seq") or index),
                        "type": normalized_event["type"],
                        "provider": str(normalized_event.get("provider"))
                        if normalized_event.get("provider")
                        else None,
                        "role": str(normalized_event.get("role"))
                        if normalized_event.get("role")
                        else None,
                        "agent": str(item.get("agent")) if item.get("agent") else None,
                        "run_id": str(normalized_event.get("run_id"))
                        if normalized_event.get("run_id")
                        else None,
                        "content": str(normalized_event.get("content"))
                        if normalized_event.get("content") is not None
                        else None,
                        "artifact_id": str(item.get("artifact_id"))
                        if item.get("artifact_id")
                        else None,
                        "timestamp": normalized_event.get("timestamp"),
                        "ts": item.get("ts"),
                        "data": normalized_event,
                    }
                )
            return normalized

        raw_messages = archive.get("messages")
        if not isinstance(raw_messages, list):
            return []

        normalized_messages: list[dict[str, Any]] = []
        for index, item in enumerate(raw_messages, start=1):
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "system")
            event_type = {
                "user": "user.message",
                "assistant": "message_finalized",
                "system": "system",
            }.get(role, "system")
            content = str(item.get("content") or "")
            normalized_messages.append(
                {
                    "seq": index,
                    "type": event_type,
                    "provider": str(item.get("provider"))
                    if item.get("provider")
                    else None,
                    "role": str(item.get("agent_role"))
                    if item.get("agent_role")
                    else None,
                    "agent": str(item.get("provider"))
                    if item.get("provider")
                    else None,
                    "run_id": None,
                    "content": content,
                    "artifact_id": None,
                    "timestamp": item.get("timestamp"),
                    "ts": item.get("timestamp"),
                    "data": {"content": content},
                }
            )
        return normalized_messages

    @staticmethod
    def _normalize_import_path(raw_path: str) -> str:
        return str(Path(raw_path).expanduser().resolve())

    @staticmethod
    def _parse_ts(value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            pass
        with contextlib.suppress(ValueError):
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        return None

    @staticmethod
    def _slugify(text: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
        normalized = normalized.strip("-")
        return normalized[:48]


class JsonRpcBridge:
    """Line-delimited JSON-RPC 2.0 server over stdio."""

    def __init__(self, runtime: DesktopRuntime | None = None) -> None:
        self.runtime = runtime or DesktopRuntime()
        self._handlers: dict[str, Handler] = {}
        self._running = False
        self._stdout_lock = asyncio.Lock()

    def method(self, name: str) -> Callable[[Handler], Handler]:
        def decorator(fn: Handler) -> Handler:
            self._handlers[name] = fn
            return fn

        return decorator

    async def start(self) -> None:
        self._running = True
        await self.runtime.initialize()
        while self._running:
            line = await asyncio.to_thread(sys.stdin.buffer.readline)
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            await self._handle_line(text)

    async def stop(self) -> None:
        self._running = False
        await self.runtime.shutdown()

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        await self._write_message(
            {"jsonrpc": "2.0", "method": method, "params": params}
        )

    async def _handle_line(self, line: str) -> None:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            return
        if not isinstance(message, dict):
            return

        method = str(message.get("method", ""))
        request_id = message.get("id")
        params = message.get("params") or {}
        handler = self._handlers.get(method)
        if handler is None:
            if request_id is not None:
                await self._write_message(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}",
                        },
                    }
                )
            return

        try:
            result = await handler(params if isinstance(params, dict) else {})
        except Exception as exc:
            if request_id is not None:
                await self._write_message(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32000, "message": str(exc)},
                    }
                )
            return

        if request_id is not None:
            await self._write_message(
                {"jsonrpc": "2.0", "id": request_id, "result": result}
            )

    async def _write_message(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, ensure_ascii=False)
        async with self._stdout_lock:
            sys.stdout.write(payload + "\n")
            sys.stdout.flush()


bridge = JsonRpcBridge()


@bridge.method("ping")
async def ping(_: JsonValue) -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "triad-desktop",
        "version": "0.1.0",
    }


@bridge.method("project.open")
async def project_open(params: JsonValue) -> dict[str, Any]:
    path = str(params.get("path", ""))
    return await bridge.runtime.open_project(path)


@bridge.method("project.list")
async def project_list(_: JsonValue) -> dict[str, Any]:
    return {"projects": await bridge.runtime.list_projects()}


@bridge.method("app.get_state")
async def app_get_state(_: JsonValue) -> dict[str, Any]:
    return await bridge.runtime.get_app_state()


@bridge.method("session.create")
async def session_create(params: JsonValue) -> dict[str, Any]:
    project_path = str(params.get("project_path", ""))
    mode = str(params.get("mode", "solo"))
    provider = str(params.get("provider", "claude"))
    title = params.get("title")
    return await bridge.runtime.create_session(
        project_path=project_path,
        mode=mode,
        provider=provider,
        title=str(title) if title else None,
    )


@bridge.method("session.list")
async def session_list(params: JsonValue) -> dict[str, Any]:
    project_path = params.get("project_path")
    return {
        "sessions": await bridge.runtime.list_sessions(
            project_path=str(project_path) if project_path else None
        )
    }


@bridge.method("session.get")
async def session_get(params: JsonValue) -> dict[str, Any]:
    session_id = str(params.get("session_id", ""))
    if not session_id:
        raise ValueError("session_id is required")
    return await bridge.runtime.get_session(session_id)


@bridge.method("session.fork")
async def session_fork(params: JsonValue) -> dict[str, Any]:
    session_id = str(params.get("session_id", ""))
    title = params.get("title")
    if not session_id:
        raise ValueError("session_id is required")
    return await bridge.runtime.fork_session(
        session_id,
        title=str(title) if title else None,
    )


@bridge.method("session.export")
async def session_export(params: JsonValue) -> dict[str, Any]:
    session_id = str(params.get("session_id", ""))
    format_name = str(params.get("format", "archive"))
    output_path = params.get("path")
    if not session_id:
        raise ValueError("session_id is required")
    return await bridge.runtime.export_session(
        session_id,
        format_name=format_name,
        output_path=str(output_path) if output_path else None,
    )


@bridge.method("session.import")
async def session_import(params: JsonValue) -> dict[str, Any]:
    input_path = str(params.get("path", ""))
    if not input_path:
        raise ValueError("path is required")
    return await bridge.runtime.import_session(input_path)


@bridge.method("session.send")
async def session_send(params: JsonValue) -> dict[str, Any]:
    session_id = str(params.get("session_id", ""))
    content = str(params.get("content", ""))
    project_path = params.get("project_path")
    provider = params.get("provider")
    model = params.get("model")
    if not session_id:
        raise ValueError("session_id is required")
    if not content.strip():
        raise ValueError("content is required")
    return await bridge.runtime.send_session_message(
        session_id=session_id,
        content=content,
        project_path=str(project_path) if project_path else None,
        provider=str(provider) if provider else None,
        model=str(model) if model else None,
    )


@bridge.method("session.stop")
async def session_stop(params: JsonValue) -> dict[str, Any]:
    session_id = str(params.get("session_id", ""))
    if not session_id:
        raise ValueError("session_id is required")
    return await bridge.runtime.stop_session(session_id)


@bridge.method("critic.start")
async def critic_start(params: JsonValue) -> dict[str, Any]:
    session_id = str(params.get("session_id", ""))
    prompt = str(params.get("prompt", ""))
    project_path = params.get("project_path")
    writer_provider = params.get("writer")
    critic_provider = params.get("critic")
    max_rounds = int(params.get("max_rounds") or 3)
    model = params.get("model")
    if not session_id:
        raise ValueError("session_id is required")
    if not prompt.strip():
        raise ValueError("prompt is required")
    return await bridge.runtime.start_critic_session(
        session_id=session_id,
        prompt=prompt,
        project_path=str(project_path) if project_path else None,
        writer_provider=str(writer_provider) if writer_provider else None,
        critic_provider=str(critic_provider) if critic_provider else None,
        max_rounds=max_rounds,
        model=str(model) if model else None,
    )


@bridge.method("brainstorm.start")
async def brainstorm_start(params: JsonValue) -> dict[str, Any]:
    session_id = str(params.get("session_id", ""))
    prompt = str(params.get("prompt", ""))
    project_path = params.get("project_path")
    provider = params.get("provider")
    model = params.get("model")
    if not session_id:
        raise ValueError("session_id is required")
    if not prompt.strip():
        raise ValueError("prompt is required")
    return await bridge.runtime.start_brainstorm_session(
        session_id=session_id,
        prompt=prompt,
        project_path=str(project_path) if project_path else None,
        provider=str(provider) if provider else None,
        model=str(model) if model else None,
    )


@bridge.method("delegate.start")
async def delegate_start(params: JsonValue) -> dict[str, Any]:
    session_id = str(params.get("session_id", ""))
    prompt = str(params.get("prompt", ""))
    project_path = params.get("project_path")
    provider = params.get("provider")
    model = params.get("model")
    if not session_id:
        raise ValueError("session_id is required")
    if not prompt.strip():
        raise ValueError("prompt is required")
    return await bridge.runtime.start_delegate_session(
        session_id=session_id,
        prompt=prompt,
        project_path=str(project_path) if project_path else None,
        provider=str(provider) if provider else None,
        model=str(model) if model else None,
    )


@bridge.method("search")
async def search(params: JsonValue) -> dict[str, Any]:
    query = str(params.get("query", ""))
    limit = int(params.get("limit") or 50)
    return {"results": await bridge.runtime.search(query, limit)}


@bridge.method("diagnostics")
async def diagnostics(_: JsonValue) -> dict[str, Any]:
    return await bridge.runtime.get_diagnostics()


@bridge.method("terminal.create")
async def terminal_create(params: JsonValue) -> dict[str, Any]:
    manager = await bridge.runtime.get_terminal_manager()
    cwd = str(params.get("cwd") or Path.home())
    cols = int(params.get("cols") or 120)
    rows = int(params.get("rows") or 24)
    terminal_id = await manager.create(cwd=cwd, cols=cols, rows=rows)
    return {"terminal_id": terminal_id}


@bridge.method("terminal.input")
async def terminal_input(params: JsonValue) -> dict[str, Any]:
    terminal_id = str(params.get("terminal_id", ""))
    if not terminal_id:
        raise ValueError("terminal_id is required")
    raw = str(params.get("data", ""))
    payload = base64.b64decode(raw) if raw else b""
    manager = await bridge.runtime.get_terminal_manager()
    await manager.write(terminal_id, payload)
    return {"status": "ok"}


@bridge.method("terminal.resize")
async def terminal_resize(params: JsonValue) -> dict[str, Any]:
    terminal_id = str(params.get("terminal_id", ""))
    if not terminal_id:
        raise ValueError("terminal_id is required")
    cols = int(params.get("cols") or 120)
    rows = int(params.get("rows") or 24)
    manager = await bridge.runtime.get_terminal_manager()
    await manager.resize(terminal_id, cols=cols, rows=rows)
    return {"status": "ok"}


@bridge.method("terminal.close")
async def terminal_close(params: JsonValue) -> dict[str, Any]:
    terminal_id = str(params.get("terminal_id", ""))
    if not terminal_id:
        raise ValueError("terminal_id is required")
    manager = await bridge.runtime.get_terminal_manager()
    await manager.close(terminal_id)
    return {"status": "ok"}


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    async def _run() -> None:
        try:
            await bridge.start()
        finally:
            await bridge.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
