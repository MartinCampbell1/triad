from triad.core.env import runtime_env_key_allowed, build_runtime_base_env


def test_allows_path():
    assert runtime_env_key_allowed("PATH") is True


def test_allows_home():
    assert runtime_env_key_allowed("HOME") is True


def test_allows_codex_prefix():
    assert runtime_env_key_allowed("CODEX_HOME") is True


def test_allows_claude_prefix():
    assert runtime_env_key_allowed("CLAUDE_CODE_SESSION") is True


def test_blocks_random_var():
    assert runtime_env_key_allowed("MY_SECRET_TOKEN") is False


def test_blocks_empty():
    assert runtime_env_key_allowed("") is False


def test_build_base_env_filters():
    source = {
        "PATH": "/usr/bin",
        "HOME": "/Users/test",
        "SECRET": "bad",
        "CODEX_HOME": "/tmp/codex",
    }
    result = build_runtime_base_env(source)
    assert "PATH" in result
    assert "HOME" in result
    assert "CODEX_HOME" in result
    assert "SECRET" not in result


def test_build_base_env_sets_default_path():
    result = build_runtime_base_env({})
    assert "PATH" in result


def test_default_strips_anthropic_api_key():
    source = {"PATH": "/usr/bin", "ANTHROPIC_API_KEY": "sk-ant-xxx"}
    result = build_runtime_base_env(source)
    assert "ANTHROPIC_API_KEY" not in result


def test_default_strips_openai_api_key():
    source = {"PATH": "/usr/bin", "OPENAI_API_KEY": "sk-xxx"}
    result = build_runtime_base_env(source)
    assert "OPENAI_API_KEY" not in result


def test_default_strips_google_api_key():
    source = {"PATH": "/usr/bin", "GOOGLE_API_KEY": "AIza-xxx"}
    result = build_runtime_base_env(source)
    assert "GOOGLE_API_KEY" not in result


def test_explicit_allow_dangerous():
    source = {"PATH": "/usr/bin", "ANTHROPIC_API_KEY": "sk-ant-xxx"}
    result = build_runtime_base_env(source, allow_dangerous_auth=True)
    assert "ANTHROPIC_API_KEY" in result


def test_non_dangerous_prefix_keys_pass():
    source = {"PATH": "/usr/bin", "ANTHROPIC_VERSION": "2023-06-01"}
    result = build_runtime_base_env(source)
    assert "ANTHROPIC_VERSION" in result
