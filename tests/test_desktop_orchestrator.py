from pathlib import Path

import pytest

from triad.core.models import Profile
from triad.core.providers.base import StreamEvent
from triad.desktop.bridge import MemoryLedger
from triad.desktop.orchestrator import Orchestrator


class FakeAccountManager:
    def __init__(self) -> None:
        self.successes: list[tuple[str, str]] = []
        self.rate_limited: list[tuple[str, str]] = []

    def get_next(self, provider: str) -> Profile | None:
        return Profile(name=f"{provider}-acc", provider=provider, path="/tmp")

    def mark_success(self, provider: str, profile_name: str) -> None:
        self.successes.append((provider, profile_name))

    def mark_rate_limited(self, provider: str, profile_name: str) -> None:
        self.rate_limited.append((provider, profile_name))


class FakeAdapter:
    def __init__(self, events: list[StreamEvent]) -> None:
        self._events = events
        self.calls: list[dict] = []

    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        for event in self._events:
            yield event


@pytest.mark.asyncio
async def test_orchestrator_run_critic_emits_findings_and_completion(tmp_path: Path):
    events: list[dict] = []

    async def on_event(event: dict) -> None:
        events.append(event)

    writer = FakeAdapter(
        [
            StreamEvent(kind="text", text="Updated critic mode runtime."),
            StreamEvent(kind="done", data={"returncode": 0}),
        ]
    )
    critic = FakeAdapter(
        [
            StreamEvent(
                kind="text",
                text='{"status":"needs_work","lgtm":false,"issues":[{"id":"1","severity":"high","kind":"correctness","file":"desktop/src/hooks/useStreamEvents.ts","line":42,"summary":"System events are ignored.","suggested_fix":"Persist system events into the transcript store."}]}',
            ),
            StreamEvent(kind="done", data={"returncode": 0}),
        ]
    )

    account_manager = FakeAccountManager()
    orchestrator = Orchestrator(
        on_event=on_event,
        account_manager=account_manager,
        adapter_factory=lambda provider: {"claude": writer, "codex": critic}[provider],
    )

    rounds = await orchestrator.run_critic(
        session_id="sess_critic",
        prompt="Implement critic mode",
        workdir=tmp_path,
        writer_provider="claude",
        critic_provider="codex",
        max_rounds=1,
    )

    assert len(rounds) == 1
    assert rounds[0].findings[0]["severity"] == "P1"
    assert any(event["type"] == "message_finalized" and event.get("role") == "writer" for event in events)
    assert any(event["type"] == "message_finalized" and event.get("role") == "critic" for event in events)
    assert any(event["type"] == "review_finding" and event.get("file") == "desktop/src/hooks/useStreamEvents.ts" for event in events)
    assert events[-1]["type"] == "run_completed"
    assert ("claude", "claude-acc") in account_manager.successes
    assert ("codex", "codex-acc") in account_manager.successes
    assert writer.calls[0]["policy"].role == "writer"
    assert critic.calls[0]["policy"].role == "critic"


@pytest.mark.asyncio
async def test_orchestrator_marks_rate_limited_failures(tmp_path: Path):
    events: list[dict] = []

    async def on_event(event: dict) -> None:
        events.append(event)

    writer = FakeAdapter(
        [
            StreamEvent(kind="error", text="429 rate limit exceeded"),
            StreamEvent(kind="done", data={"returncode": 1}),
        ]
    )
    critic = FakeAdapter([StreamEvent(kind="done", data={"returncode": 0})])

    account_manager = FakeAccountManager()
    orchestrator = Orchestrator(
        on_event=on_event,
        account_manager=account_manager,
        adapter_factory=lambda provider: {"claude": writer, "codex": critic}[provider],
    )

    rounds = await orchestrator.run_critic(
        session_id="sess_rate_limit",
        prompt="Implement critic mode",
        workdir=tmp_path,
        writer_provider="claude",
        critic_provider="codex",
        max_rounds=1,
    )

    assert rounds == []
    assert events[-1]["type"] == "run_failed"
    assert "rate limit" in events[-1]["error"].lower()
    assert account_manager.rate_limited == [("claude", "claude-acc")]


@pytest.mark.asyncio
async def test_orchestrator_run_brainstorm_emits_ideators_and_moderator(tmp_path: Path):
    events: list[dict] = []

    async def on_event(event: dict) -> None:
        events.append(event)

    adapters = {
        "claude": FakeAdapter(
            [
                StreamEvent(kind="text", text="Idea from Claude"),
                StreamEvent(kind="done", data={"returncode": 0}),
            ]
        ),
        "codex": FakeAdapter(
            [
                StreamEvent(kind="text", text="Idea from Codex"),
                StreamEvent(kind="done", data={"returncode": 0}),
            ]
        ),
        "gemini": FakeAdapter(
            [
                StreamEvent(kind="text", text="Idea from Gemini"),
                StreamEvent(kind="done", data={"returncode": 0}),
            ]
        ),
    }

    orchestrator = Orchestrator(
        on_event=on_event,
        account_manager=FakeAccountManager(),
        adapter_factory=lambda provider: adapters[provider],
    )

    ideas = await orchestrator.run_brainstorm(
        session_id="sess_brainstorm",
        prompt="Explore options for the desktop workflow",
        workdir=tmp_path,
        ideator_providers=["claude", "codex"],
        moderator_provider="gemini",
    )

    assert len(ideas) == 3
    assert ideas[0].role == "ideator"
    assert ideas[-1].role == "moderator"
    assert any(event["type"] == "message_finalized" and event.get("role") == "ideator" for event in events)
    assert any(event["type"] == "message_finalized" and event.get("role") == "moderator" for event in events)
    assert events[-1]["type"] == "run_completed"
    assert adapters["claude"].calls[0]["policy"].role == "critic"
    assert adapters["gemini"].calls[0]["policy"].role == "critic"


@pytest.mark.asyncio
async def test_orchestrator_run_delegate_emits_live_lane_streams(tmp_path: Path):
    events: list[dict] = []

    async def on_event(event: dict) -> None:
        events.append(event)

    adapters = {
        "claude": FakeAdapter(
            [
                StreamEvent(kind="text", text="Lane output from Claude"),
                StreamEvent(kind="done", data={"returncode": 0}),
            ]
        ),
        "codex": FakeAdapter(
            [
                StreamEvent(kind="text", text="Lane output from Codex"),
                StreamEvent(kind="done", data={"returncode": 0}),
            ]
        ),
    }

    orchestrator = Orchestrator(
        on_event=on_event,
        account_manager=FakeAccountManager(),
        adapter_factory=lambda provider: adapters[provider],
    )

    lanes = await orchestrator.run_delegate(
        session_id="sess_delegate",
        prompt="Split the work into independent lanes",
        workdir=tmp_path,
        lane_providers=["claude", "codex"],
    )

    assert len(lanes) == 2
    assert all(lane.success for lane in lanes)
    assert any(
        event["type"] == "text_delta" and event.get("run_id", "").startswith("sess_delegate:delegate:")
        for event in events
    )
    assert any(
        event["type"] == "message_finalized" and event.get("role") == "delegate" for event in events
    )
    assert any(
        event["type"] == "system"
        and event.get("run_id", "").startswith("sess_delegate:delegate:")
        and "started" in event.get("content", "")
        for event in events
    )
    assert any("Delegate finished" in event.get("content", "") for event in events if event["type"] == "system")
    assert events[-1]["type"] == "run_completed"
    assert adapters["claude"].calls[0]["policy"].role == "delegate"


@pytest.mark.asyncio
async def test_memory_ledger_create_session_ids_are_unique(tmp_path: Path):
    ledger = MemoryLedger(tmp_path / "triad.db")
    await ledger.initialize()

    first = await ledger.create_session(mode="solo", task="one")
    second = await ledger.create_session(mode="solo", task="two")

    assert first != second
