from pathlib import Path

import pytest

from triad.desktop.bridge import DesktopRuntime, bridge


@pytest.mark.asyncio
async def test_desktop_runtime_fork_preserves_session_shape_and_history(tmp_path: Path):
    runtime = DesktopRuntime()
    await runtime.initialize()
    try:
        await runtime.open_project(str(tmp_path))
        source = await runtime.create_session(
            str(tmp_path),
            "critic",
            "claude",
            "Fork me",
        )
        source_id = source["id"]

        ledger = await runtime.ledger()
        await ledger.append_event(
            source_id,
            "user.message",
            {"content": "Keep this context"},
            provider="claude",
            role="user",
            content="Keep this context",
        )
        await ledger.append_event(
            source_id,
            "message_finalized",
            {"content": "First answer"},
            provider="claude",
            role="writer",
            content="First answer",
        )

        forked = await runtime.fork_session(source_id, title="Fork me too")

        assert forked["project_path"] == source["project_path"]
        assert forked["mode"] == source["mode"]
        assert forked["provider"] == source["provider"]
        assert forked["title"] == "Fork me too"
        assert forked["id"] != source_id

        source_after = await runtime.get_session(source_id)
        fork_after = await runtime.get_session(forked["id"])

        assert source_after["session"]["title"] == "Fork me"
        assert any(message["content"] == "First answer" for message in source_after["messages"])
        assert any(message["content"] == "Keep this context" for message in fork_after["messages"])
        assert any(message["content"] == "First answer" for message in fork_after["messages"])
        assert fork_after["messages"] != []
        assert fork_after["session"]["message_count"] >= source_after["session"]["message_count"]
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_desktop_runtime_fork_does_not_mutate_source_session(tmp_path: Path):
    runtime = DesktopRuntime()
    await runtime.initialize()
    try:
        await runtime.open_project(str(tmp_path))
        source = await runtime.create_session(
            str(tmp_path),
            "solo",
            "claude",
            "Source session",
        )
        source_id = source["id"]
        ledger = await runtime.ledger()
        await ledger.append_event(
            source_id,
            "user.message",
            {"content": "Original history"},
            provider="claude",
            role="user",
            content="Original history",
        )

        source_before = await runtime.get_session(source_id)
        forked = await runtime.fork_session(source_id)
        source_after = await runtime.get_session(source_id)
        fork_after = await runtime.get_session(forked["id"])

        assert source_before == source_after
        assert fork_after["session"]["project_path"] == source_before["session"]["project_path"]
        assert any(message["content"] == "Original history" for message in fork_after["messages"])
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_bridge_session_fork_surface_is_available(tmp_path: Path):
    runtime = DesktopRuntime()
    await runtime.initialize()
    previous_runtime = bridge.runtime
    bridge.runtime = runtime
    try:
        await runtime.open_project(str(tmp_path))
        source = await runtime.create_session(
            str(tmp_path),
            "delegate",
            "claude",
            "Bridge fork source",
        )

        result = await bridge._handlers["session.fork"](
            {
                "session_id": source["id"],
                "title": "Bridge fork copy",
            }
        )

        assert result["project_path"] == source["project_path"]
        assert result["mode"] == source["mode"]
        assert result["provider"] == source["provider"]
        assert result["title"] == "Bridge fork copy"

        hydrated = await runtime.get_session(result["id"])
        assert hydrated["session"]["id"] == result["id"]
    finally:
        bridge.runtime = previous_runtime
        await runtime.shutdown()
