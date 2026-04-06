import asyncio
import json
from pathlib import Path

import pytest

from triad.desktop.bridge import DesktopRuntime
from triad.desktop.event_merger import EventMerger
from triad.desktop.file_watcher import ClaudeSessionWatcher


@pytest.mark.asyncio
async def test_claude_session_watcher_emits_authoritative_assistant_messages(tmp_path: Path):
    events: list[dict] = []

    async def on_event(event: dict) -> None:
        events.append(event)

    claude_projects_dir = tmp_path / ".claude" / "projects"
    project_dir = tmp_path / "workspace"
    project_dir.mkdir(parents=True)
    storage_dir = claude_projects_dir / ClaudeSessionWatcher.project_path_to_storage_dir(str(project_dir))
    storage_dir.mkdir(parents=True)
    session_file = storage_dir / "session.jsonl"

    watcher = ClaudeSessionWatcher(
        on_event=on_event,
        claude_projects_dir=claude_projects_dir,
        poll_interval=0.01,
    )
    watcher.watch_session("sess_live", str(project_dir))
    session_file.write_text(
        json.dumps(
            {
                "uuid": "assistant-1",
                "timestamp": "2026-04-06T12:00:00Z",
                "sessionId": "claude-session-1",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Clean answer from watcher."},
                    ],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    await watcher.scan_once()
    await watcher.scan_once()

    assert len(events) == 1
    assert events[0]["type"] == "authoritative_message"
    assert events[0]["session_id"] == "sess_live"
    assert events[0]["content"] == "Clean answer from watcher."
    assert events[0]["claude_session_id"] == "claude-session-1"


@pytest.mark.asyncio
async def test_claude_session_watcher_prefers_prompt_matching_file(tmp_path: Path):
    events: list[dict] = []

    async def on_event(event: dict) -> None:
        events.append(event)

    claude_projects_dir = tmp_path / ".claude" / "projects"
    project_dir = tmp_path / "workspace"
    project_dir.mkdir(parents=True)
    storage_dir = claude_projects_dir / ClaudeSessionWatcher.project_path_to_storage_dir(str(project_dir))
    storage_dir.mkdir(parents=True)

    older_file = storage_dir / "older.jsonl"
    newer_file = storage_dir / "newer.jsonl"
    older_file.write_text(
        json.dumps(
            {
                "uuid": "assistant-older",
                "timestamp": "2026-04-06T12:00:00Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Correct prompt match."}],
                },
                "lastPrompt": "Implement the critical fix",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    newer_file.write_text(
        json.dumps(
            {
                "uuid": "assistant-newer",
                "timestamp": "2026-04-06T12:00:00Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Wrong file."}],
                },
                "lastPrompt": "Something else",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    newer_file.touch()

    watcher = ClaudeSessionWatcher(on_event=on_event, claude_projects_dir=claude_projects_dir)
    watcher.watch_session("sess_live", str(project_dir), prompt_hint="Implement the critical fix")
    await watcher.scan_once()

    assert len(events) == 1
    assert events[0]["content"] == "Correct prompt match."


@pytest.mark.asyncio
async def test_event_merger_prefers_authoritative_message_over_pty_buffer():
    events: list[dict] = []

    async def on_event(event: dict) -> None:
        events.append(event)

    merger = EventMerger(on_ui_event=on_event, authoritative_delay_sec=0.02)
    await merger.handle(
        {
            "source": "pty",
            "type": "text_delta",
            "session_id": "sess_merge",
            "provider": "claude",
            "delta": "raw draft ",
        }
    )
    await merger.handle(
        {
            "source": "pty",
            "type": "run_completed",
            "session_id": "sess_merge",
            "provider": "claude",
        }
    )
    await merger.handle(
        {
            "source": "file_watcher",
            "type": "authoritative_message",
            "session_id": "sess_merge",
            "provider": "claude",
            "role": "assistant",
            "content": "Clean final answer",
            "message_id": "assistant-42",
        }
    )
    await asyncio.sleep(0.03)

    finalized = [event for event in events if event["type"] == "message_finalized"]
    assert len(finalized) == 1
    assert finalized[0]["content"] == "Clean final answer"
    assert finalized[0]["source"] == "file_watcher"
    assert finalized[0]["authoritative"] is True
    assert events[-1]["type"] == "run_completed"
    assert all(event.get("content") != "raw draft" for event in finalized)


class _FakeClaudePTY:
    def __init__(self, workdir: Path, on_event, env=None) -> None:
        self.workdir = workdir
        self.on_event = on_event
        self.env = env
        self.started = False
        self.sent: list[str] = []

    async def start(self) -> None:
        self.started = True

    async def send(self, text: str) -> None:
        self.sent.append(text)

    async def stop(self) -> None:
        self.started = False


class _FakeWatcher:
    def __init__(self) -> None:
        self.watched: list[tuple[str, str]] = []
        self.unwatched: list[str] = []

    def watch_session(self, session_id: str, project_path: str, *, prompt_hint: str | None = None) -> None:
        self.watched.append((session_id, project_path))

    def unwatch_session(self, session_id: str) -> None:
        self.unwatched.append(session_id)

    def snapshot(self) -> list[dict]:
        return []

    async def stop(self) -> None:
        return None


@pytest.mark.asyncio
async def test_runtime_tracks_claude_session_in_file_watcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runtime = DesktopRuntime()
    await runtime.initialize()
    monkeypatch.setattr("triad.desktop.bridge.ClaudePTY", _FakeClaudePTY)
    fake_watcher = _FakeWatcher()
    runtime._file_watcher = fake_watcher
    try:
        await runtime.open_project(str(tmp_path))
        session = await runtime.create_session(str(tmp_path), "solo", "claude", "Watch me")

        result = await runtime.send_session_message(session["id"], "Hello watcher", provider="claude")

        assert result["provider"] == "claude"
        assert fake_watcher.watched == [(session["id"], str(tmp_path.resolve()))]
        runtime_session = runtime._sessions[session["id"]]
        assert runtime_session.pty is not None
        assert runtime_session.pty.started is True
        assert runtime_session.pty.sent
    finally:
        await runtime.shutdown()
