from unittest.mock import MagicMock
from triad.core.modes.critic import CriticMode, CriticConfig
from triad.core.context.blackboard import Blackboard
from triad.core.models import Profile


def test_swap_changes_real_mode_state():
    writer_adapter = MagicMock()
    writer_adapter.provider = "claude"
    critic_adapter = MagicMock()
    critic_adapter.provider = "codex"

    writer_profile = Profile(name="acc1", provider="claude", path="/tmp/c")
    critic_profile = Profile(name="acc1", provider="codex", path="/tmp/x")

    config = CriticConfig(writer_provider="claude", critic_provider="codex")
    mode = CriticMode(
        config=config,
        writer_adapter=writer_adapter,
        critic_adapter=critic_adapter,
        writer_profile=writer_profile,
        critic_profile=critic_profile,
        ledger=MagicMock(),
        blackboard=Blackboard(task="test"),
    )

    mode.swap_roles()

    assert mode.config.writer_provider == "codex"
    assert mode.config.critic_provider == "claude"
    assert mode.writer_adapter is critic_adapter
    assert mode.critic_adapter is writer_adapter
    assert mode.writer_profile is critic_profile
    assert mode.critic_profile is writer_profile


def test_swap_twice_returns_to_original():
    writer_adapter = MagicMock()
    critic_adapter = MagicMock()
    config = CriticConfig(writer_provider="claude", critic_provider="codex")
    mode = CriticMode(
        config=config,
        writer_adapter=writer_adapter,
        critic_adapter=critic_adapter,
        writer_profile=Profile(name="a", provider="claude", path="/tmp"),
        critic_profile=Profile(name="b", provider="codex", path="/tmp"),
        ledger=MagicMock(),
        blackboard=Blackboard(task="test"),
    )

    mode.swap_roles()
    mode.swap_roles()

    assert mode.config.writer_provider == "claude"
    assert mode.config.critic_provider == "codex"
