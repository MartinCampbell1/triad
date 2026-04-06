from pathlib import Path

from triad.core.config import (
    DEFAULT_CONFIG,
    TriadConfig,
    get_default_config_path,
    get_default_profiles_dir,
    get_default_triad_home,
    load_config,
    save_config,
)


def test_default_config():
    cfg = TriadConfig()
    assert cfg.default_mode == "critic"
    assert cfg.default_writer == "claude"
    assert cfg.default_critic == "codex"
    assert cfg.cooldown_base_sec == 300
    assert cfg.providers_priority == ["codex", "claude", "gemini"]
    assert cfg.critic_max_rounds == 5
    assert cfg.delegate_timeout == 1800


def test_config_profiles_dir():
    cfg = TriadConfig()
    assert cfg.profiles_dir == Path.home() / ".cli-profiles"


def test_config_db_path():
    cfg = TriadConfig()
    assert cfg.db_path == cfg.triad_home / "triad.db"


def test_default_paths_honor_env(monkeypatch):
    monkeypatch.setenv("TRIAD_HOME", "/tmp/triad-home")
    monkeypatch.setenv("TRIAD_PROFILES_DIR", "/tmp/triad-profiles")

    assert get_default_triad_home() == Path("/tmp/triad-home")
    assert get_default_profiles_dir() == Path("/tmp/triad-profiles")
    assert get_default_config_path() == Path("/tmp/triad-home/config.yaml")


def test_load_config_creates_default(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    cfg = load_config(config_path)
    assert cfg.default_mode == "critic"
    assert config_path.exists()


def test_save_and_load_config(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    cfg = TriadConfig(
        default_mode="solo",
        cooldown_base_sec=900,
        providers_priority=["claude", "codex"],
        critic_max_rounds=3,
        triad_home=tmp_path / "triad-home",
        profiles_dir=tmp_path / "profiles",
    )
    save_config(cfg, config_path)
    loaded = load_config(config_path)
    assert loaded.default_mode == "solo"
    assert loaded.cooldown_base_sec == 900
    assert loaded.providers_priority == ["claude", "codex"]
    assert loaded.critic_max_rounds == 3
    assert loaded.triad_home == tmp_path / "triad-home"
    assert loaded.profiles_dir == tmp_path / "profiles"


def test_load_config_preserves_unknown_fields(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("default_mode: delegate\ncustom_field: hello\n")
    cfg = load_config(config_path)
    assert cfg.default_mode == "delegate"
