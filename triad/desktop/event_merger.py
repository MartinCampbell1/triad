"""Merge low-level desktop events into UI-friendly stream events."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


UiEventHandler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(slots=True)
class EventMerger:
    """Normalize and route events from PTY, hooks, and file watchers."""

    on_ui_event: UiEventHandler
    authoritative_delay_sec: float = 0.9
    _text_buffer: dict[str, str] = field(default_factory=dict)
    _pending_completion: dict[str, asyncio.Task] = field(default_factory=dict)
    _authoritative_ids: set[str] = field(default_factory=set)
    _provisional_message_ids: dict[str, str] = field(default_factory=dict)
    _failed_sessions: set[str] = field(default_factory=set)
    _completed_sessions: set[str] = field(default_factory=set)

    async def handle(self, event: dict[str, Any]) -> None:
        source = str(event.get("source", "unknown"))
        event_type = str(event.get("type", ""))
        session_id = str(event.get("session_id", ""))
        provider = event.get("provider")

        if source == "pty":
            await self._handle_pty_event(session_id, provider, event)
            return

        if source == "hooks":
            await self._handle_hooks_event(session_id, provider, event)
            return

        if source == "file_watcher":
            await self._handle_file_watcher_event(session_id, provider, event)
            return

        await self._emit(
            {
                "type": event_type or "system",
                "session_id": session_id,
                "provider": provider,
                "source": source,
                **{k: v for k, v in event.items() if k != "source"},
            }
        )

    async def flush(self, session_id: str | None = None) -> None:
        if session_id is None:
            sessions = list(self._text_buffer)
        else:
            sessions = [session_id]

        for sid in sessions:
            pending = self._text_buffer.pop(sid, "").strip()
            if not pending:
                continue
            message_id = f"provisional:{sid}:{uuid.uuid4().hex[:8]}"
            self._provisional_message_ids[sid] = message_id
            await self._emit(
                {
                    "type": "message_finalized",
                    "session_id": sid,
                    "provider": "claude",
                    "source": "pty",
                    "content": pending,
                    "message_id": message_id,
                }
            )
        if session_id is None:
            targets = list(self._pending_completion)
        else:
            targets = [session_id]
        current_task = asyncio.current_task()
        for sid in targets:
            task = self._pending_completion.pop(sid, None)
            if task is not None and task is not current_task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def _handle_pty_event(
        self,
        session_id: str,
        provider: Any,
        event: dict[str, Any],
    ) -> None:
        event_type = str(event.get("type", ""))
        if event_type == "text_delta":
            delta = str(event.get("delta", ""))
            if not delta:
                return
            self._failed_sessions.discard(session_id)
            self._completed_sessions.discard(session_id)
            self._text_buffer[session_id] = (
                self._text_buffer.get(session_id, "") + delta
            )
            await self._emit(
                {
                    "type": "text_delta",
                    "session_id": session_id,
                    "provider": provider or "claude",
                    "source": "pty",
                    "delta": delta,
                }
            )
            return

        if event_type in {"run_completed", "run_failed"}:
            if event_type == "run_failed":
                self._failed_sessions.add(session_id)
                self._completed_sessions.discard(session_id)
                await self.flush(session_id)
                await self._emit(
                    {
                        "type": event_type,
                        "session_id": session_id,
                        "provider": provider or "claude",
                        "source": "pty",
                        **{k: v for k, v in event.items() if k != "source"},
                    }
                )
                return

            if session_id in self._completed_sessions:
                return
            self._failed_sessions.discard(session_id)
            self._completed_sessions.discard(session_id)
            await self._schedule_pending_completion(
                session_id,
                {
                    "type": event_type,
                    "session_id": session_id,
                    "provider": provider or "claude",
                    "source": "pty",
                    **{k: v for k, v in event.items() if k != "source"},
                },
            )
            return

        await self._emit(
            {
                "type": event_type or "system",
                "session_id": session_id,
                "provider": provider or "claude",
                "source": "pty",
                **{k: v for k, v in event.items() if k != "source"},
            }
        )

    async def _handle_hooks_event(
        self,
        session_id: str,
        provider: Any,
        event: dict[str, Any],
    ) -> None:
        hook = str(event.get("hook", event.get("type", "")))
        tool = str(event.get("tool", event.get("name", "unknown")))

        if hook in {"pre_tool", "pre_tool_use", "tool_start"}:
            await self._emit(
                {
                    "type": "tool_use",
                    "session_id": session_id,
                    "provider": provider or "claude",
                    "source": "hooks",
                    "tool": tool,
                    "input": event.get("input", event.get("payload", {})),
                    **{k: v for k, v in event.items() if k != "source"},
                }
            )
            return

        if hook in {"post_tool", "post_tool_use", "tool_result"}:
            await self._emit(
                {
                    "type": "tool_result",
                    "session_id": session_id,
                    "provider": provider or "claude",
                    "source": "hooks",
                    "tool": tool,
                    "output": event.get("output", event.get("payload", {})),
                    "success": bool(event.get("success", True)),
                    **{k: v for k, v in event.items() if k != "source"},
                }
            )
            return

        if hook in {"stop", "run_completed", "done"}:
            await self.flush(session_id)
            self._completed_sessions.add(session_id)
            await self._emit(
                {
                    "type": "run_completed",
                    "session_id": session_id,
                    "provider": provider or "claude",
                    "source": "hooks",
                    **{k: v for k, v in event.items() if k != "source"},
                }
            )
            return

        await self._emit(
            {
                "type": "system",
                "session_id": session_id,
                "provider": provider or "claude",
                "source": "hooks",
                **{k: v for k, v in event.items() if k != "source"},
            }
        )

    async def _handle_file_watcher_event(
        self,
        session_id: str,
        provider: Any,
        event: dict[str, Any],
    ) -> None:
        event_type = str(event.get("type", ""))
        if event_type != "authoritative_message":
            await self._emit(
                {
                    "type": event_type or "system",
                    "session_id": session_id,
                    "provider": provider or "claude",
                    "source": "file_watcher",
                    **{k: v for k, v in event.items() if k != "source"},
                }
            )
            return

        message_id = str(event.get("message_id") or "").strip()
        if message_id and message_id in self._authoritative_ids:
            return
        if message_id:
            self._authoritative_ids.add(message_id)

        completion = self._pending_completion.pop(session_id, None)
        if completion is not None:
            completion.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await completion

        self._text_buffer.pop(session_id, None)
        effective_message_id = self._provisional_message_ids.pop(
            session_id,
            message_id or f"authoritative:{session_id}:{uuid.uuid4().hex[:8]}",
        )
        await self._emit(
            {
                "type": "message_finalized",
                "session_id": session_id,
                "provider": provider or "claude",
                "source": "file_watcher",
                "content": str(event.get("content") or ""),
                "role": event.get("role"),
                "timestamp": event.get("timestamp"),
                "message_id": effective_message_id,
                "authoritative": True,
            }
        )
        if (
            session_id not in self._failed_sessions
            and session_id not in self._completed_sessions
        ):
            self._completed_sessions.add(session_id)
            await self._emit(
                {
                    "type": "run_completed",
                    "session_id": session_id,
                    "provider": provider or "claude",
                    "source": "file_watcher",
                    "authoritative": True,
                }
            )

    async def _schedule_pending_completion(
        self,
        session_id: str,
        completion_event: dict[str, Any],
    ) -> None:
        current = self._pending_completion.pop(session_id, None)
        if current is not None:
            current.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await current

        if not self._text_buffer.get(session_id, "").strip():
            await self._emit(completion_event)
            return

        async def delayed_emit() -> None:
            try:
                await asyncio.sleep(self.authoritative_delay_sec)
                await self.flush(session_id)
                await self._emit(completion_event)
                self._completed_sessions.add(session_id)
            finally:
                self._pending_completion.pop(session_id, None)

        self._pending_completion[session_id] = asyncio.create_task(delayed_emit())

    async def _emit(self, event: dict[str, Any]) -> None:
        await self.on_ui_event(event)
