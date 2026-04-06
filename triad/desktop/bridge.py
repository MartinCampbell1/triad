"""JSON-RPC bridge between the Tauri desktop shell and Python backend."""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from triad.core.accounts.manager import AccountManager
from triad.core.capabilities import CapabilityRegistry
from triad.core.config import get_default_config_path, load_config
from triad.core.providers import get_adapter

from .claude_pty import ClaudePTY
from .file_watcher import ClaudeSessionWatcher
from .search import SearchIndex
from .terminal_manager import TerminalManager
from .services.attachments import materialize_attachments
from .services.diagnostics import build_runtime_diagnostics
from .services.session_compare import build_session_compare
from .services.session_compare import build_session_replay
from .services.session_transfer import build_session_archive
from .services.session_transfer import build_session_messages
from .services.session_transfer import derive_fork_title
from .services.session_transfer import derive_title
from .services.session_transfer import format_ts
from .services.session_transfer import load_config_json
from .services.session_transfer import normalize_import_events
from .services.session_transfer import normalize_import_path
from .services.session_transfer import parse_ts
from .services.session_transfer import resolve_export_path
from .services.session_transfer import render_session_markdown
from .services.session_transfer import restore_imported_events
from .services.session_transfer import restore_imported_session_metadata
from .services.timeline import build_session_timeline
from .services.review_actions import apply_review_patch as apply_review_patch_service
from .services.rpc_handlers import register_non_terminal_handlers
from .services.session_service import build_contextual_prompt as build_contextual_prompt_service
from .services.session_service import build_session_payload as build_session_payload_service
from .services.session_service import count_events as count_events_service
from .services.session_service import count_messages as count_messages_service
from .services.session_service import create_session as create_session_service
from .services.session_service import export_session as export_session_service
from .services.session_service import fork_session as fork_session_service
from .services.session_service import get_session as get_session_service
from .services.session_service import get_session_events as get_session_events_service
from .services.session_service import highlight_snippet as highlight_snippet_service
from .services.session_service import hydrate_session_runtime as hydrate_session_runtime_service
from .services.session_service import import_session as import_session_service
from .services.session_service import list_sessions as list_sessions_service
from .services.session_service import search_memory as search_memory_service
from .services.session_service import derive_title_from_input
from .services.run_sessions import default_critic_provider as default_critic_provider_service
from .services.run_sessions import ensure_event_pipeline as ensure_event_pipeline_service
from .services.run_sessions import get_orchestrator as get_orchestrator_service
from .services.run_sessions import handle_stream_event as handle_stream_event_service
from .services.run_sessions import persist_ui_event as persist_ui_event_service
from .services.run_sessions import prepare_mode_session as prepare_mode_session_service
from .services.run_sessions import run_headless as run_headless_service
from .services.run_sessions import start_brainstorm_session as start_brainstorm_session_service
from .services.run_sessions import start_critic_session as start_critic_session_service
from .services.run_sessions import start_delegate_session as start_delegate_session_service
from .services.terminal_rpc import register_terminal_handlers
from .services.terminal_host import terminal_host_terminal_id, terminal_host_title

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
    linked_terminal_id: str | None = None
    active_run_id: str | None = None
    transcript_capture: str = "typed"


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
        rows = sorted(self._sessions.values(), key=lambda row: row["updated_at"], reverse=True)
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

    async def get_session_events(self, session_id: str, limit: int = 500) -> list[dict[str, Any]]:
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
        self.session_runtime_factory = SessionRuntime
        self._background_tasks: set[asyncio.Task] = set()
        self._session_tasks: dict[str, set[asyncio.Task]] = {}
        self._capabilities = CapabilityRegistry()

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
        await ledger.save_project(str(project_path), project_path.name, str(project_path))
        return {
            "path": str(project_path),
            "name": project_path.name,
            "git_root": str(project_path),
        }

    async def list_projects(self) -> list[dict[str, Any]]:
        ledger = await self.ledger()
        rows = await ledger.list_projects()
        return [
            {
                "path": row["path"],
                "name": row.get("name") or row.get("display_name") or Path(row["path"]).name,
                "git_root": row["git_root"],
                "last_opened_at": format_ts(row.get("last_opened_at")),
            }
            for row in rows
        ]

    async def create_session(
        self,
        project_path: str,
        mode: str,
        provider: str = "claude",
        title: str | None = None,
    ) -> dict[str, Any]:
        return await create_session_service(
            self,
            self.session_runtime_factory,
            project_path,
            mode,
            provider=provider,
            title=title,
        )

    async def list_sessions(self, project_path: str | None = None) -> list[dict[str, Any]]:
        return await list_sessions_service(self, project_path=project_path)

    async def get_app_state(self) -> dict[str, Any]:
        projects = await self.list_projects()
        sessions = await self.list_sessions()
        last_project = projects[0]["path"] if projects else None
        preferred_session = (
            next((session for session in sessions if session["project_path"] == last_project), None)
            if last_project
            else None
        )
        last_session_id = (preferred_session or (sessions[0] if sessions else None) or {}).get("id")
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
        return await export_session_service(
            self,
            session_id,
            format_name=format_name,
            output_path=output_path,
        )

    async def import_session(self, input_path: str) -> dict[str, Any]:
        return await import_session_service(
            self,
            self.session_runtime_factory,
            input_path,
        )

    async def fork_session(
        self,
        source_session_id: str,
        *,
        title: str | None = None,
    ) -> dict[str, Any]:
        return await fork_session_service(
            self,
            self.session_runtime_factory,
            source_session_id,
            title=title,
        )

    async def send_session_message(
        self,
        session_id: str,
        content: str,
        project_path: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        attachments: Any = None,
    ) -> dict[str, Any]:
        ledger = await self.ledger()
        runtime = self._sessions.get(session_id)
        if runtime is None:
            runtime = await self._hydrate_session(session_id, project_path=project_path)
            self._sessions[session_id] = runtime
        selected_provider = (provider or runtime.provider or "claude").strip()
        runtime.provider = selected_provider
        runtime.state = "running"
        if selected_provider != "claude":
            runtime.transcript_capture = "typed"
        has_live_context = selected_provider == "claude" and runtime.pty is not None
        resolved_attachments = materialize_attachments(
            attachments,
            project_path=runtime.project_path,
            artifacts_dir=self.config.artifacts_dir,
            session_id=session_id,
        )

        await ledger.append_event(
            session_id,
            "user.message",
            {"content": content, "attachments": resolved_attachments},
            provider=selected_provider,
            role="user",
            content=content,
        )

        existing = await ledger.get_session(session_id)
        existing_title = (existing or {}).get("title")
        if not existing_title:
            new_title = derive_title_from_input(content, resolved_attachments)
            await ledger.update_session_title(session_id, new_title)
            runtime.title = new_title

        effective_prompt = await self._build_contextual_prompt(
            session_id,
            content,
            provider=selected_provider,
            has_live_context=has_live_context,
            latest_attachments=resolved_attachments,
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

            run_id = f"{session_id}:interactive:{uuid.uuid4().hex[:8]}"
            terminal_id = await self._ensure_terminal_host_link(
                session_id,
                runtime,
                provider=selected_provider,
                run_id=run_id,
            )

            async def on_pty_event(event: dict[str, Any]) -> None:
                active_run_id = runtime.active_run_id or run_id
                linked_terminal_id = runtime.linked_terminal_id or terminal_id
                enriched = {
                    **event,
                    "run_id": active_run_id,
                    "linked_terminal_id": linked_terminal_id,
                    "transcript_mode": runtime.transcript_capture,
                }
                if enriched.get("type") == "text_delta":
                    await self._append_terminal_host_output(runtime, str(enriched.get("delta") or ""))
                await self._handle_stream_event(session_id, enriched)
                if enriched.get("type") in {"run_completed", "run_failed"}:
                    await self._finish_terminal_host_run(runtime)

            claude = runtime.pty
            if claude is None:
                claude = ClaudePTY(
                    workdir=Path(runtime.project_path),
                    on_event=on_pty_event,
                    env=env,
                )
                runtime.pty = claude
                await claude.start()
            else:
                claude.on_event = on_pty_event

            await claude.send(effective_prompt)
            return {"status": "sent", "session_id": session_id, "provider": "claude"}

        if runtime.pty is not None:
            with contextlib.suppress(Exception):
                await runtime.pty.stop()
            runtime.pty = None
        await self._detach_terminal_host(runtime)
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
        task.add_done_callback(lambda completed: self._discard_task(session_id, completed))
        return {"status": "sent", "session_id": session_id, "provider": selected_provider}

    async def stop_session(self, session_id: str) -> dict[str, Any]:
        runtime = self._sessions.get(session_id)
        if runtime and runtime.pty is not None:
            await runtime.pty.stop()
            runtime.pty = None
            await self._detach_terminal_host(runtime)
            runtime.state = "stopped"
        if self._file_watcher is not None:
            self._file_watcher.unwatch_session(session_id)
        for task in list(self._session_tasks.get(session_id, set())):
            task.cancel()
        ledger = await self.ledger()
        await ledger.update_session_status(session_id, "completed")
        return {"status": "stopped", "session_id": session_id}

    async def get_session(self, session_id: str) -> dict[str, Any]:
        return await get_session_service(self, session_id)

    async def compare_sessions(
        self,
        left_session_id: str,
        right_session_id: str,
    ) -> dict[str, Any]:
        return await build_session_compare(self, left_session_id, right_session_id)

    async def replay_session(self, session_id: str) -> dict[str, Any]:
        return await build_session_replay(self, session_id)

    async def apply_review_patch(self, session_id: str, patch: str) -> dict[str, Any]:
        ledger = await self.ledger()
        row = await ledger.get_session(session_id)
        if row is None:
            raise ValueError(f"Unknown session: {session_id}")
        runtime = self._sessions.get(session_id) or await self._hydrate_session(session_id)
        self._sessions[session_id] = runtime
        project_path = str(
            Path(row.get("project_path") or runtime.project_path)
            .expanduser()
            .resolve()
        )
        result = apply_review_patch_service(project_path, patch)
        summary = result.get("diff_stat") or result.get("status_text") or "Patch applied."
        await self.emit_ui_event(
            {
                "session_id": session_id,
                "type": "system",
                "provider": runtime.provider,
                "title": "Review patch applied",
                "content": f"{summary}",
            }
        )
        return result

    async def abandon_review(self, session_id: str) -> dict[str, Any]:
        ledger = await self.ledger()
        row = await ledger.get_session(session_id)
        if row is None:
            raise ValueError(f"Unknown session: {session_id}")
        runtime = self._sessions.get(session_id) or await self._hydrate_session(session_id)
        self._sessions[session_id] = runtime
        await self.emit_ui_event(
            {
                "session_id": session_id,
                "type": "system",
                "provider": runtime.provider,
                "title": "Review dismissed",
                "content": "Review patch was abandoned.",
            }
        )
        return {"status": "ok", "session_id": session_id}

    async def get_orchestrator(self) -> Any:
        return await get_orchestrator_service(self)

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
        attachments: Any = None,
    ) -> tuple[SessionRuntime, str]:
        return await prepare_mode_session_service(
            self,
            session_id=session_id,
            prompt=prompt,
            project_path=project_path,
            mode=mode,
            provider=provider,
            attachments=attachments,
        )

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
        attachments: Any = None,
    ) -> dict[str, Any]:
        return await start_critic_session_service(
            self,
            session_id=session_id,
            prompt=prompt,
            project_path=project_path,
            writer_provider=writer_provider,
            critic_provider=critic_provider,
            max_rounds=max_rounds,
            model=model,
            attachments=attachments,
        )

    async def start_brainstorm_session(
        self,
        *,
        session_id: str,
        prompt: str,
        project_path: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        attachments: Any = None,
    ) -> dict[str, Any]:
        return await start_brainstorm_session_service(
            self,
            session_id=session_id,
            prompt=prompt,
            project_path=project_path,
            provider=provider,
            model=model,
            attachments=attachments,
        )

    async def start_delegate_session(
        self,
        *,
        session_id: str,
        prompt: str,
        project_path: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        attachments: Any = None,
    ) -> dict[str, Any]:
        return await start_delegate_session_service(
            self,
            session_id=session_id,
            prompt=prompt,
            project_path=project_path,
            provider=provider,
            model=model,
            attachments=attachments,
        )

    async def _ensure_event_pipeline(self) -> None:
        await ensure_event_pipeline_service(self)

    async def _handle_stream_event(self, session_id: str, event: dict[str, Any]) -> None:
        await handle_stream_event_service(self, session_id, event)

    async def _run_headless(
        self,
        *,
        session_id: str,
        prompt: str,
        provider: str,
        model: str | None,
        workdir: Path,
    ) -> None:
        await run_headless_service(
            self,
            session_id=session_id,
            prompt=prompt,
            provider=provider,
            model=model,
            workdir=workdir,
        )

    async def get_terminal_manager(self) -> TerminalManager:
        if self._terminal_manager is None:
            manager: TerminalManager | None = None

            async def on_output(terminal_id: str, data: bytes) -> None:
                session = manager.get_session(terminal_id) if manager is not None else None
                event: dict[str, Any] = {
                    "type": "terminal_output",
                    "terminal_id": terminal_id,
                    "data": base64.b64encode(data).decode("ascii"),
                }
                if session is not None:
                    event["terminal_kind"] = session.kind
                    if session.linked_session_id:
                        event["session_id"] = session.linked_session_id
                    if session.linked_run_id:
                        event["run_id"] = session.linked_run_id
                    if session.linked_provider:
                        event["provider"] = session.linked_provider
                    if session.transcript_mode:
                        event["transcript_mode"] = session.transcript_mode
                await self.emit_ui_event(
                    event
                )

            manager = TerminalManager(on_output=on_output)
            self._terminal_manager = manager
        return self._terminal_manager

    async def _runtime_for_terminal(self, terminal_id: str) -> tuple[Any, SessionRuntime | None]:
        manager = await self.get_terminal_manager()
        session = manager.get_session(terminal_id)
        if session is None:
            raise KeyError(f"Unknown terminal session: {terminal_id}")
        if session.kind != "provider" or not session.linked_session_id:
            return session, None

        runtime = self._sessions.get(session.linked_session_id)
        if runtime is None:
            runtime = await self._hydrate_session(session.linked_session_id)
            self._sessions[session.linked_session_id] = runtime
        return session, runtime

    async def _activate_terminal_host_run(
        self,
        session_id: str,
        runtime: SessionRuntime,
        *,
        provider: str,
        terminal_id: str | None = None,
    ) -> str:
        run_id = runtime.active_run_id or f"{session_id}:interactive:{uuid.uuid4().hex[:8]}"
        manager = await self.get_terminal_manager()
        linked_terminal_id = terminal_id or runtime.linked_terminal_id or terminal_host_terminal_id(session_id)
        manager.update_session(
            linked_terminal_id,
            status="ready",
            linked_run_id=run_id,
            linked_provider=provider,
            transcript_mode="partial",
        )
        runtime.linked_terminal_id = linked_terminal_id
        runtime.active_run_id = run_id
        runtime.transcript_capture = "partial"
        return run_id

    async def _ensure_terminal_host_link(
        self,
        session_id: str,
        runtime: SessionRuntime,
        *,
        provider: str,
        run_id: str,
    ) -> str:
        manager = await self.get_terminal_manager()
        title = terminal_host_title(runtime.title, provider)
        terminal = await manager.ensure_provider_session(
            session_id=session_id,
            cwd=runtime.project_path,
            title=title,
            provider=provider,
            run_id=run_id,
            terminal_id=runtime.linked_terminal_id or terminal_host_terminal_id(session_id),
        )
        runtime.linked_terminal_id = terminal.terminal_id
        await self._activate_terminal_host_run(
            session_id,
            runtime,
            provider=provider,
            terminal_id=terminal.terminal_id,
        )
        return terminal.terminal_id

    async def handle_terminal_input(self, terminal_id: str, data: bytes) -> dict[str, Any]:
        session, runtime = await self._runtime_for_terminal(terminal_id)
        if runtime is None:
            manager = await self.get_terminal_manager()
            await manager.write(terminal_id, data)
            return {"status": "ok", "source": "shell"}

        if runtime.pty is None:
            return {"status": "unavailable", "source": "provider", "terminal_id": terminal_id}

        await self._activate_terminal_host_run(
            runtime.session_id,
            runtime,
            provider=runtime.provider or "claude",
            terminal_id=terminal_id,
        )
        await runtime.pty.write(data)
        return {"status": "ok", "source": "provider", "terminal_id": terminal_id}

    async def handle_terminal_resize(self, terminal_id: str, cols: int, rows: int) -> dict[str, Any]:
        manager = await self.get_terminal_manager()
        await manager.resize(terminal_id, cols=cols, rows=rows)
        session, runtime = await self._runtime_for_terminal(terminal_id)
        if runtime is None or runtime.pty is None:
            return {"status": "ok", "source": "shell" if runtime is None else "provider", "terminal_id": terminal_id}

        await runtime.pty.resize(cols, rows)
        return {"status": "ok", "source": "provider", "terminal_id": terminal_id}

    async def _append_terminal_host_output(
        self,
        runtime: SessionRuntime,
        delta: str,
    ) -> None:
        if not delta or not runtime.linked_terminal_id:
            return
        manager = await self.get_terminal_manager()
        with contextlib.suppress(KeyError):
            await manager.capture_output(runtime.linked_terminal_id, delta.encode("utf-8"))

    async def _finish_terminal_host_run(
        self,
        runtime: SessionRuntime,
        *,
        status: str = "unavailable",
    ) -> None:
        if not runtime.linked_terminal_id or self._terminal_manager is None:
            runtime.active_run_id = None
            return
        with contextlib.suppress(KeyError):
            self._terminal_manager.update_session(
                runtime.linked_terminal_id,
                status=status,
                linked_run_id="",
            )
        runtime.active_run_id = None

    async def _detach_terminal_host(
        self,
        runtime: SessionRuntime,
    ) -> None:
        await self._finish_terminal_host_run(runtime)

    async def _hydrate_session(
        self,
        session_id: str,
        project_path: str | None = None,
    ) -> SessionRuntime:
        return await hydrate_session_runtime_service(
            self,
            self.session_runtime_factory,
            session_id,
            project_path=project_path,
        )

    async def _count_events(self, session_id: str) -> int:
        return await count_events_service(self, session_id)

    async def _count_messages(self, session_id: str) -> int:
        return await count_messages_service(self, session_id)

    async def _get_session_events(self, session_id: str, limit: int = 500) -> list[dict[str, Any]]:
        return await get_session_events_service(self, session_id, limit)

    async def _build_contextual_prompt(
        self,
        session_id: str,
        latest_user_content: str,
        *,
        provider: str,
        has_live_context: bool,
        latest_attachments: list[dict[str, Any]] | None = None,
    ) -> str:
        return await build_contextual_prompt_service(
            self,
            session_id,
            latest_user_content,
            provider=provider,
            has_live_context=has_live_context,
            latest_attachments=latest_attachments,
        )

    def _session_payload(
        self,
        runtime: SessionRuntime,
        session_row: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return build_session_payload_service(self, runtime, session_row=session_row)

    async def _restore_imported_events(
        self,
        session_id: str,
        events: list[dict[str, Any]],
    ) -> None:
        ledger = await self.ledger()
        await restore_imported_events(ledger, session_id, events)

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
        await restore_imported_session_metadata(
            ledger,
            session_id=session_id,
            mode=mode,
            task=task,
            title=title,
            project_path=project_path,
            status=status,
            config_json=config_json,
            created_at=created_at,
            updated_at=updated_at,
        )

    async def _persist_ui_event(self, event: dict[str, Any]) -> None:
        await persist_ui_event_service(self, event)

    async def emit_ui_event(self, event: dict[str, Any]) -> None:
        await self._persist_ui_event(event)
        await bridge.notify("event.stream", event)

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
        return await build_runtime_diagnostics(self)

    @staticmethod
    def _load_config_json(raw: Any) -> dict[str, Any]:
        return load_config_json(raw)

    @staticmethod
    def _derive_title(content: str) -> str:
        return derive_title(content)

    @staticmethod
    def _derive_fork_title(source_title: str) -> str:
        return derive_fork_title(source_title)

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
        return format_ts(value)

    def _default_critic_provider(self, writer_provider: str) -> str:
        return default_critic_provider_service(self, writer_provider)

    @staticmethod
    def _search_memory(
        ledger: MemoryLedger,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        return search_memory_service(ledger, query, limit)

    @staticmethod
    def _highlight_snippet(content: str, start: int, length: int) -> str:
        return highlight_snippet_service(content, start, length)

    def _resolve_export_path(
        self,
        title: str,
        session_id: str,
        format_name: str,
        output_path: str | None,
    ) -> Path:
        return resolve_export_path(self.config.exports_dir, title, session_id, format_name, output_path)

    @staticmethod
    def _normalize_import_events(archive: dict[str, Any]) -> list[dict[str, Any]]:
        return normalize_import_events(archive)

    @staticmethod
    def _normalize_import_path(raw_path: str) -> str:
        return normalize_import_path(raw_path)

    @staticmethod
    def _parse_ts(value: Any) -> float | None:
        return parse_ts(value)

    @staticmethod
    def _slugify(text: str) -> str:
        return slugify(text)


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
        await self._write_message({"jsonrpc": "2.0", "method": method, "params": params})

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
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
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
            await self._write_message({"jsonrpc": "2.0", "id": request_id, "result": result})

    async def _write_message(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, ensure_ascii=False)
        async with self._stdout_lock:
            sys.stdout.write(payload + "\n")
            sys.stdout.flush()


bridge = JsonRpcBridge()
register_terminal_handlers(bridge)
register_non_terminal_handlers(bridge)


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
