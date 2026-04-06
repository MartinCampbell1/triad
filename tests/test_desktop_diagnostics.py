from pathlib import Path
from types import SimpleNamespace

import pytest

import triad.desktop.bridge as bridge


class FakeAccountManager:
    def pool_status(self, provider: str) -> list[dict]:
        return [
            {
                "name": f"{provider}-acc1",
                "available": provider != "gemini",
                "requests_made": 3,
                "errors": 1,
                "cooldown_remaining_sec": 0,
            }
        ]


class FakeTerminalManager:
    async def list_active(self) -> list[str]:
        return ["term_1", "term_2"]


@pytest.mark.asyncio
async def test_desktop_runtime_diagnostics_shape(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(bridge, "get_default_config_path", lambda: tmp_path / "config.yaml")
    monkeypatch.setattr(
        bridge,
        "load_config",
        lambda _path: SimpleNamespace(
            triad_home=tmp_path / "triad-home",
            db_path=tmp_path / "triad-home" / "triad.db",
            profiles_dir=tmp_path / "profiles",
            cooldown_base_sec=300,
        ),
    )

    runtime = bridge.DesktopRuntime()
    runtime.account_manager = FakeAccountManager()
    runtime._terminal_manager = FakeTerminalManager()
    runtime._hook_listener = SimpleNamespace(socket_path=tmp_path / "triad-hooks.sock")
    runtime._sessions = {
        "session-1": bridge.SessionRuntime(
            session_id="session-1",
            project_path=str(tmp_path / "project"),
            mode="solo",
            provider="claude",
            title="Smoke",
            pty=object(),
            state="active",
        )
    }

    diagnostics = await runtime.get_diagnostics()

    assert set(
        diagnostics
    ) >= {
        "version",
        "python_version",
        "triad_home",
        "db_path",
        "providers",
        "active_claude_sessions",
        "active_sessions",
        "active_terminals",
        "hooks_socket",
    }
    assert diagnostics["triad_home"] == str(tmp_path / "triad-home")
    assert diagnostics["db_path"] == str(tmp_path / "triad-home" / "triad.db")
    assert set(diagnostics["providers"]) == {"claude", "codex", "gemini"}
    assert all(isinstance(diagnostics["providers"][provider], list) for provider in diagnostics["providers"])
    assert diagnostics["active_claude_sessions"] == ["session-1"]
    assert diagnostics["active_sessions"] == [
        {
            "id": "session-1",
            "mode": "solo",
            "provider": "claude",
            "project_path": str(tmp_path / "project"),
            "state": "active",
        }
    ]
    assert diagnostics["active_terminals"] == ["term_1", "term_2"]
    assert diagnostics["hooks_socket"] == str(tmp_path / "triad-hooks.sock")
