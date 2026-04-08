from pathlib import Path
from triad.core.models import Profile
from triad.core.providers.claude import ClaudeAdapter
from triad.core.providers.codex import CodexAdapter
from triad.core.providers.gemini import GeminiAdapter


def test_claude_headless_command():
    adapter = ClaudeAdapter()
    cmd = adapter.headless_command("Fix the bug")
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "Fix the bug" in cmd
    assert "--output-format" in cmd


def test_claude_headless_command_with_resume():
    adapter = ClaudeAdapter()
    cmd = adapter.headless_command("Continue", session_id="sess_abc")
    assert "--resume" in cmd
    assert "sess_abc" in cmd


def test_claude_interactive_command():
    adapter = ClaudeAdapter()
    cmd = adapter.interactive_command()
    assert cmd == ["claude"]


def test_claude_build_env_sets_home(tmp_path: Path):
    profile = Profile(name="acc1", provider="claude", path=str(tmp_path / "acc1"))
    (tmp_path / "acc1" / "home").mkdir(parents=True)
    adapter = ClaudeAdapter()
    env = adapter.build_env(profile, base_env={"PATH": "/usr/bin"})
    assert env["HOME"] == str(tmp_path / "acc1" / "home")


def test_codex_headless_command():
    adapter = CodexAdapter()
    cmd = adapter.headless_command("Review this code")
    assert cmd[0] == "codex"
    assert "exec" in cmd
    assert "--json" in cmd
    assert "--full-auto" in cmd
    assert "Review this code" in cmd


def test_codex_stream_json_tool_event_is_parsed():
    adapter = CodexAdapter()
    events = adapter.parse_stream_line(
        '{"type":"tool_started","name":"Read","args":{"path":"src/App.tsx"}}'
    )
    assert len(events) == 1
    assert events[0].kind == "tool_use"
    assert events[0].data["tool"] == "Read"


def test_codex_build_env_sets_codex_home(tmp_path: Path):
    profile = Profile(name="acc1", provider="codex", path=str(tmp_path / "acc1"))
    adapter = CodexAdapter()
    env = adapter.build_env(profile, base_env={"PATH": "/usr/bin"})
    assert env["CODEX_HOME"] == str(tmp_path / "acc1")


def test_gemini_headless_command():
    adapter = GeminiAdapter()
    cmd = adapter.headless_command("Brainstorm ideas")
    assert cmd[0] == "gemini"
    assert "-p" in cmd
    assert "Brainstorm ideas" in cmd


def test_gemini_build_env_sets_home(tmp_path: Path):
    profile = Profile(name="acc1", provider="gemini", path=str(tmp_path / "acc1"))
    (tmp_path / "acc1" / "home").mkdir(parents=True)
    adapter = GeminiAdapter()
    env = adapter.build_env(profile, base_env={"PATH": "/usr/bin"})
    assert env["HOME"] == str(tmp_path / "acc1" / "home")


def test_get_adapter():
    from triad.core.providers import get_adapter

    assert isinstance(get_adapter("claude"), ClaudeAdapter)
    assert isinstance(get_adapter("codex"), CodexAdapter)
    assert isinstance(get_adapter("gemini"), GeminiAdapter)
