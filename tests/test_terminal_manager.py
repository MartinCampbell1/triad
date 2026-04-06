from pathlib import Path

import pytest

import triad.desktop.bridge as bridge_module
from triad.desktop.terminal_manager import TerminalManager
from triad.desktop.terminal_manager import TerminalSession


@pytest.mark.asyncio
async def test_terminal_manager_lists_sessions_with_snapshot_and_clear(monkeypatch, tmp_path: Path):
    async def fake_start(self):
        self._running = True
        self.status = "ready"
        self.created_at = self.created_at or "2026-04-07T10:00:00"
        self.updated_at = self.updated_at or "2026-04-07T10:00:00"

    async def on_output(_terminal_id: str, _data: bytes) -> None:
        return None

    monkeypatch.setattr(TerminalSession, "start", fake_start, raising=False)

    manager = TerminalManager(on_output=on_output)
    first = await manager.create(tmp_path, title="Project shell")
    second = await manager.create(tmp_path, title="Aux shell")

    first_session = manager.get_session(first.terminal_id)
    second_session = manager.get_session(second.terminal_id)
    assert first_session is not None
    assert second_session is not None

    first_session.append_output(b"hello")
    first_session.updated_at = "2026-04-07T10:00:05"
    second_session.updated_at = "2026-04-07T10:00:04"

    await manager.clear(first.terminal_id)
    assert first_session.snapshot() == ""

    first_session.append_output(b"world")
    first_session.updated_at = "2026-04-07T10:00:06"

    sessions = manager.list_sessions()

    assert [row["terminal_id"] for row in sessions] == [first.terminal_id, second.terminal_id]
    assert sessions[0]["title"] == "Project shell"
    assert sessions[0]["cwd"] == str(tmp_path.resolve())
    assert sessions[0]["status"] == "ready"
    assert sessions[0]["snapshot"].endswith("world")
    assert sessions[1]["title"] == "Aux shell"


@pytest.mark.asyncio
async def test_terminal_bridge_methods_return_listable_session_metadata(monkeypatch, tmp_path: Path):
    class FakeSession:
        terminal_id = "term_fake"

        def describe(self):
            return {
                "terminal_id": self.terminal_id,
                "title": "Docs shell",
                "cwd": str(tmp_path.resolve()),
                "command": ["/bin/zsh", "-l"],
                "shell": "/bin/zsh",
                "status": "ready",
                "created_at": "2026-04-07T10:00:00",
                "updated_at": "2026-04-07T10:00:01",
                "last_output_at": None,
                "snapshot": "prompt> ",
            }

    class FakeManager:
        def __init__(self) -> None:
            self.create_kwargs: dict[str, object] | None = None
            self.clear_calls: list[str] = []

        async def create(self, **kwargs):
            self.create_kwargs = kwargs
            return FakeSession()

        def list_sessions(self):
            return [FakeSession().describe()]

        async def clear(self, terminal_id: str):
            self.clear_calls.append(terminal_id)

    fake_manager = FakeManager()

    async def get_terminal_manager():
        return fake_manager

    monkeypatch.setattr(bridge_module.bridge.runtime, "get_terminal_manager", get_terminal_manager)

    created = await bridge_module.bridge._handlers["terminal.create"](
        {
            "cwd": str(tmp_path),
            "title": "Docs shell",
            "cols": 100,
            "rows": 40,
        }
    )
    listed = await bridge_module.bridge._handlers["terminal.list"]({})
    cleared = await bridge_module.bridge._handlers["terminal.clear"]({"terminal_id": "term_fake"})

    assert created["terminal_id"] == "term_fake"
    assert created["session"]["title"] == "Docs shell"
    assert fake_manager.create_kwargs == {
        "cwd": str(tmp_path),
        "cols": 100,
        "rows": 40,
        "title": "Docs shell",
    }
    assert listed["sessions"][0]["snapshot"] == "prompt> "
    assert cleared == {"status": "ok"}
    assert fake_manager.clear_calls == ["term_fake"]


@pytest.mark.asyncio
async def test_terminal_manager_supports_provider_linkage_and_buffer_capture(tmp_path: Path):
    outputs: list[tuple[str, bytes]] = []

    async def on_output(terminal_id: str, data: bytes) -> None:
        outputs.append((terminal_id, data))

    manager = TerminalManager(on_output=on_output)
    linked = await manager.ensure_provider_session(
        session_id="sess_live",
        cwd=tmp_path,
        title="Claude live · Session",
        provider="claude",
        run_id="sess_live:interactive:run_1",
    )

    await manager.capture_output(linked.terminal_id, b"draft response")
    manager.update_session(linked.terminal_id, status="unavailable", linked_run_id="")
    sessions = manager.list_sessions()

    assert linked.virtual is True
    assert sessions[0]["kind"] == "provider"
    assert sessions[0]["linked_session_id"] == "sess_live"
    assert sessions[0]["linked_provider"] == "claude"
    assert sessions[0]["transcript_mode"] == "partial"
    assert sessions[0]["status"] == "unavailable"
    assert sessions[0]["snapshot"].endswith("draft response")
    assert outputs == [(linked.terminal_id, b"draft response")]
