from triad.core.policy import PolicyGuard


def test_check_no_api_key_ok():
    guard = PolicyGuard()
    warnings = guard.check_environment({"PATH": "/usr/bin", "HOME": "/tmp"})
    assert len(warnings) == 0


def test_check_warns_on_anthropic_api_key():
    guard = PolicyGuard()
    warnings = guard.check_environment({"ANTHROPIC_API_KEY": "sk-ant-xxx"})
    assert any("ANTHROPIC_API_KEY" in w for w in warnings)


def test_check_warns_on_openai_api_key():
    guard = PolicyGuard()
    warnings = guard.check_environment({"OPENAI_API_KEY": "sk-xxx"})
    assert any("OPENAI_API_KEY" in w for w in warnings)
    assert any("Stripped" in w for w in warnings)
