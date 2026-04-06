from __future__ import annotations

from pathlib import Path

from triad.core import provider_sessions


class _FakeNamedTempFile:
    def __init__(self, path: Path):
        self.name = str(path)
        self._handle = path.open("w", encoding="utf-8")

    def write(self, data: str) -> int:
        return self._handle.write(data)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._handle.close()


def test_open_login_terminal_uses_command_script_on_darwin(monkeypatch, tmp_path: Path):
    launched: list[tuple[list[str], dict]] = []
    script_path = tmp_path / "triad-codex-login.command"

    monkeypatch.setattr(provider_sessions.sys, "platform", "darwin")
    monkeypatch.setattr(
        provider_sessions.tempfile,
        "NamedTemporaryFile",
        lambda **kwargs: _FakeNamedTempFile(script_path),
    )
    monkeypatch.setattr(
        provider_sessions.subprocess,
        "Popen",
        lambda args, **kwargs: launched.append((list(args), kwargs)),
    )

    command = provider_sessions.open_login_terminal("codex", cwd=Path("/tmp/workspace"))

    assert command == "codex login"
    assert launched == [(["open", "-a", "Terminal", str(script_path)], {})]

    content = script_path.read_text(encoding="utf-8")
    assert "codex login" in content
    assert "cd /tmp/workspace" in content
    assert "osascript" not in content
    assert script_path.stat().st_mode & 0o700 == 0o700


def test_open_login_terminal_runs_directly_off_darwin(monkeypatch):
    launched: list[tuple[list[str], dict]] = []

    monkeypatch.setattr(provider_sessions.sys, "platform", "linux")
    monkeypatch.setattr(
        provider_sessions.subprocess,
        "Popen",
        lambda args, **kwargs: launched.append((list(args), kwargs)),
    )

    command = provider_sessions.open_login_terminal("claude", cwd=Path("/tmp/triad"))

    assert command == "claude auth login"
    assert launched == [
        (
            ["claude", "auth", "login"],
            {"cwd": "/tmp/triad"},
        )
    ]
