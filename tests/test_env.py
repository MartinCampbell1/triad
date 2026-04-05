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
