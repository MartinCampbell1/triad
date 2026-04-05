from triad.core.execution_policy import ExecutionPolicy
from triad.core.providers.claude import ClaudeAdapter
from triad.core.providers.codex import CodexAdapter


def test_writer_policy():
    policy = ExecutionPolicy.writer()
    assert policy.role == "writer"
    assert policy.sandbox == "workspace_write"


def test_critic_policy():
    policy = ExecutionPolicy.critic()
    assert policy.role == "critic"
    assert policy.sandbox == "read_only"


def test_policy_is_frozen():
    policy = ExecutionPolicy.critic()
    try:
        policy.role = "writer"
        assert False, "Should raise"
    except AttributeError:
        pass


def test_claude_writer_no_restrictions():
    adapter = ClaudeAdapter()
    policy = ExecutionPolicy.writer()
    cmd = adapter.headless_command("Fix bug", policy=policy)
    joined = " ".join(cmd)
    assert "--allowedTools" not in joined


def test_claude_critic_read_only():
    adapter = ClaudeAdapter()
    policy = ExecutionPolicy.critic()
    cmd = adapter.headless_command("Review code", policy=policy)
    joined = " ".join(cmd)
    assert "--allowedTools" in joined
    assert "Read" in joined


def test_codex_writer_full_auto():
    adapter = CodexAdapter()
    policy = ExecutionPolicy.writer()
    cmd = adapter.headless_command("Fix bug", policy=policy)
    assert "--full-auto" in cmd


def test_codex_critic_read_only():
    adapter = CodexAdapter()
    policy = ExecutionPolicy.critic()
    cmd = adapter.headless_command("Review code", policy=policy)
    joined = " ".join(cmd)
    assert "read-only" in joined
    assert "--full-auto" not in cmd


def test_no_policy_defaults_to_full_auto():
    adapter = CodexAdapter()
    cmd = adapter.headless_command("Fix bug")
    assert "--full-auto" in cmd
