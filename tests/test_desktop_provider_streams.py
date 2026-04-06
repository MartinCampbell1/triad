import pytest

from triad.core.providers.base import StreamEvent
from triad.desktop.services.provider_streams import ProviderStreamRelay


async def _stream(events: list[StreamEvent]):
    for event in events:
        yield event


@pytest.mark.asyncio
async def test_provider_stream_relay_emits_canonical_events_and_collects_output():
    emitted: list[dict] = []

    async def on_event(event: dict) -> None:
        emitted.append(event)

    relay = ProviderStreamRelay(
        session_id="sess_1",
        provider="codex",
        run_id="run_1",
        role="writer",
        on_event=on_event,
    )
    outcome = await relay.consume(
        _stream(
            [
                StreamEvent(kind="text", text="hello"),
                StreamEvent(kind="tool_use", data={"tool": "Read", "input": {"path": "a.txt"}}),
                StreamEvent(kind="tool_result", data={"tool": "Read", "output": "ok", "status": "completed"}),
                StreamEvent(kind="done", data={"returncode": 0}),
            ]
        )
    )

    assert outcome.output == "hello"
    assert outcome.stdout == "hello"
    assert outcome.returncode == 0
    assert outcome.error_text == ""
    assert emitted == [
        {
            "session_id": "sess_1",
            "provider": "codex",
            "run_id": "run_1",
            "role": "writer",
            "type": "text_delta",
            "delta": "hello",
        },
        {
            "session_id": "sess_1",
            "provider": "codex",
            "run_id": "run_1",
            "role": "writer",
            "type": "tool_use",
            "tool": "Read",
            "input": {"path": "a.txt"},
        },
        {
            "session_id": "sess_1",
            "provider": "codex",
            "run_id": "run_1",
            "role": "writer",
            "type": "tool_result",
            "tool": "Read",
            "output": "ok",
            "status": "completed",
        },
    ]


@pytest.mark.asyncio
async def test_provider_stream_relay_can_collect_output_without_text_deltas():
    emitted: list[dict] = []

    async def on_event(event: dict) -> None:
        emitted.append(event)

    relay = ProviderStreamRelay(
        session_id="sess_2",
        provider="claude",
        on_event=on_event,
        stream_text=False,
    )
    outcome = await relay.consume(
        _stream(
            [
                StreamEvent(kind="text", text="part one"),
                StreamEvent(kind="text", text="part two"),
                StreamEvent(kind="error", text="warning"),
                StreamEvent(kind="done", data={"returncode": 17}),
            ]
        )
    )

    assert outcome.output == "part one\npart two"
    assert outcome.stdout == "part one\npart two"
    assert outcome.error_text == "warning"
    assert outcome.stderr == "warning"
    assert outcome.returncode == 17
    assert emitted == []


@pytest.mark.asyncio
async def test_provider_stream_relay_tracks_done_metadata_and_stderr():
    emitted: list[dict] = []

    async def on_event(event: dict) -> None:
        emitted.append(event)

    relay = ProviderStreamRelay(
        session_id="sess_3",
        provider="gemini",
        run_id="run_3",
        role="critic",
        on_event=on_event,
    )
    outcome = await relay.consume(
        _stream(
            [
                StreamEvent(kind="error", text="stderr line"),
                StreamEvent(kind="done", data={"returncode": 12, "timed_out": True, "rate_limited": True}),
            ]
        )
    )

    assert outcome.output == ""
    assert outcome.stderr == "stderr line"
    assert outcome.error_text == "stderr line"
    assert outcome.returncode == 12
    assert outcome.timed_out is True
    assert outcome.rate_limited is True
    assert emitted == []
