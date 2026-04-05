from triad.core.capabilities import CapabilityRegistry


def test_claude_interactive_has_full_tui():
    reg = CapabilityRegistry()
    assert reg.supports("claude", "interactive", "full_tui") is True


def test_claude_headless_no_full_tui():
    reg = CapabilityRegistry()
    assert reg.supports("claude", "headless", "full_tui") is False


def test_claude_headless_has_stream_json():
    reg = CapabilityRegistry()
    assert reg.supports("claude", "headless", "stream_json") is True


def test_codex_headless_has_exec():
    reg = CapabilityRegistry()
    assert reg.supports("codex", "headless", "exec") is True


def test_unknown_provider():
    reg = CapabilityRegistry()
    assert reg.supports("unknown", "headless", "exec") is False
