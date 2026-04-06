from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from triad.core.providers.base import StreamEvent


UiEventHandler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(slots=True)
class ProviderStreamOutcome:
    output: str
    stderr: str = ""
    errors: list[str] = field(default_factory=list)
    returncode: int | None = None
    timed_out: bool = False
    rate_limited: bool = False

    @property
    def error_text(self) -> str:
        if self.stderr.strip():
            return self.stderr.strip()
        return "\n".join(part for part in self.errors if part).strip()

    @property
    def stdout(self) -> str:
        return self.output


@dataclass(slots=True)
class ProviderStreamRelay:
    session_id: str
    provider: str
    on_event: UiEventHandler
    run_id: str | None = None
    role: str | None = None
    stream_text: bool = True
    chunks: list[str] = field(default_factory=list)
    stderr_chunks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    returncode: int | None = None
    timed_out: bool = False
    rate_limited: bool = False

    async def consume(self, stream: AsyncIterator[StreamEvent]) -> ProviderStreamOutcome:
        async for event in stream:
            await self.handle(event)
        return ProviderStreamOutcome(
            output="\n".join(part for part in self.chunks if part).strip(),
            stderr="\n".join(part for part in self.stderr_chunks if part).strip(),
            errors=list(self.errors),
            returncode=self.returncode,
            timed_out=self.timed_out,
            rate_limited=self.rate_limited,
        )

    async def handle(self, event: StreamEvent) -> None:
        if event.kind == "text" and event.text:
            self.chunks.append(event.text)
            if self.stream_text:
                await self.emit({"type": "text_delta", "delta": event.text})
            return

        if event.kind == "tool_use":
            payload = event.data or {}
            await self.emit({"type": "tool_use", **payload})
            return

        if event.kind == "tool_result":
            payload = event.data or {}
            await self.emit({"type": "tool_result", **payload})
            return

        if event.kind == "error" and event.text:
            self.errors.append(event.text)
            self.stderr_chunks.append(event.text)
            return

        if event.kind == "done":
            payload = event.data or {}
            raw_returncode = payload.get("returncode")
            if isinstance(raw_returncode, int):
                self.returncode = raw_returncode
            raw_stdout = payload.get("stdout")
            if isinstance(raw_stdout, str) and raw_stdout and not self.chunks:
                self.chunks.append(raw_stdout)
            raw_stderr = payload.get("stderr")
            if isinstance(raw_stderr, str) and raw_stderr:
                self.stderr_chunks.append(raw_stderr)
            raw_timed_out = payload.get("timed_out")
            if isinstance(raw_timed_out, bool):
                self.timed_out = raw_timed_out
            raw_rate_limited = payload.get("rate_limited")
            if isinstance(raw_rate_limited, bool):
                self.rate_limited = raw_rate_limited

    async def emit(self, payload: dict[str, Any]) -> None:
        event = {
            "session_id": self.session_id,
            "provider": self.provider,
            **payload,
        }
        if self.run_id:
            event["run_id"] = self.run_id
        if self.role:
            event["role"] = self.role
        await self.on_event(event)
