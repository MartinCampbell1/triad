from pathlib import Path
from triad.core.config import TriadConfig, load_config, save_config, DEFAULT_CONFIG


def test_default_config():
    cfg = TriadConfig()
    assert cfg.default_mode == "critic"
    assert cfg.default_writer == "claude"
    assert cfg.default_critic == "codex"
    assert cfg.critic_max_rounds == 5
    assert cfg.delegate_timeout == 1800


def test_config_profiles_dir():
    cfg = TriadConfig()
    assert cfg.profiles_dir == Path.home() / ".cli-profiles"


def test_config_db_path():
    cfg = TriadConfig()
    assert cfg.db_path == Path.home() / ".triad" / "triad.db"


def test_load_config_creates_default(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    cfg = load_config(config_path)
    assert cfg.default_mode == "critic"
    assert config_path.exists()


def test_save_and_load_config(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    cfg = TriadConfig(default_mode="solo", critic_max_rounds=3)
    save_config(cfg, config_path)
    loaded = load_config(config_path)
    assert loaded.default_mode == "solo"
    assert loaded.critic_max_rounds == 3


def test_load_config_preserves_unknown_fields(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("default_mode: delegate\ncustom_field: hello\n")
    cfg = load_config(config_path)
    assert cfg.default_mode == "delegate"
