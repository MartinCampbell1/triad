"""Configuration management for Triad runtime paths and YAML config."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def get_default_profiles_dir() -> Path:
    """Return the default profiles directory, honoring TRIAD_PROFILES_DIR."""
    override = os.environ.get("TRIAD_PROFILES_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cli-profiles"


def get_default_triad_home() -> Path:
    """Return the Triad home directory, honoring TRIAD_HOME."""
    override = os.environ.get("TRIAD_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".triad"


def get_default_config_path() -> Path:
    """Return the default config path inside the active Triad home."""
    return get_default_triad_home() / "config.yaml"


@dataclass
class TriadConfig:
    """Triad configuration."""

    # Defaults
    default_mode: str = "critic"
    default_writer: str = "claude"
    default_critic: str = "codex"

    # Paths
    profiles_dir: Path = field(default_factory=get_default_profiles_dir)
    triad_home: Path = field(default_factory=get_default_triad_home)

    # Account/runtime policy
    cooldown_base_sec: int = 300
    providers_priority: list[str] = field(default_factory=lambda: ["codex", "claude", "gemini"])

    # Orchestration
    critic_max_rounds: int = 5
    brainstorm_max_rounds: int = 3
    delegate_timeout: int = 1800
    intervention_enabled: bool = True

    # Brainstorm participants
    brainstorm_participants: list[dict] = field(default_factory=lambda: [
        {"provider": "gemini", "role": "ideator"},
        {"provider": "claude", "role": "builder"},
        {"provider": "codex", "role": "skeptic"},
    ])

    @property
    def db_path(self) -> Path:
        return self.triad_home / "triad.db"

    @property
    def artifacts_dir(self) -> Path:
        return self.triad_home / "artifacts"

    @property
    def worktrees_dir(self) -> Path:
        return self.triad_home / "worktrees"

    @property
    def exports_dir(self) -> Path:
        return self.triad_home / "exports"


DEFAULT_CONFIG = TriadConfig()


def _serialize_config(cfg: TriadConfig) -> dict:
    """Convert config to a dict suitable for YAML serialization."""
    d = {}
    d["default_mode"] = cfg.default_mode
    d["default_writer"] = cfg.default_writer
    d["default_critic"] = cfg.default_critic
    d["profiles_dir"] = str(cfg.profiles_dir)
    d["triad_home"] = str(cfg.triad_home)
    d["cooldown_base_sec"] = cfg.cooldown_base_sec
    d["providers_priority"] = cfg.providers_priority
    d["critic_max_rounds"] = cfg.critic_max_rounds
    d["brainstorm_max_rounds"] = cfg.brainstorm_max_rounds
    d["delegate_timeout"] = cfg.delegate_timeout
    d["intervention_enabled"] = cfg.intervention_enabled
    d["brainstorm_participants"] = cfg.brainstorm_participants
    return d


def save_config(cfg: TriadConfig, path: Path) -> None:
    """Save config to YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _serialize_config(cfg)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def load_config(path: Path) -> TriadConfig:
    """Load config from YAML file. Creates default if missing."""
    if not path.exists():
        cfg = TriadConfig()
        save_config(cfg, path)
        return cfg

    data = yaml.safe_load(path.read_text()) or {}

    kwargs = {}
    if "default_mode" in data:
        kwargs["default_mode"] = data["default_mode"]
    if "default_writer" in data:
        kwargs["default_writer"] = data["default_writer"]
    if "default_critic" in data:
        kwargs["default_critic"] = data["default_critic"]
    if "profiles_dir" in data:
        kwargs["profiles_dir"] = Path(data["profiles_dir"])
    if "triad_home" in data:
        kwargs["triad_home"] = Path(data["triad_home"])
    if "cooldown_base_sec" in data:
        kwargs["cooldown_base_sec"] = int(data["cooldown_base_sec"])
    if "providers_priority" in data:
        kwargs["providers_priority"] = list(data["providers_priority"])
    if "critic_max_rounds" in data:
        kwargs["critic_max_rounds"] = int(data["critic_max_rounds"])
    if "brainstorm_max_rounds" in data:
        kwargs["brainstorm_max_rounds"] = int(data["brainstorm_max_rounds"])
    if "delegate_timeout" in data:
        kwargs["delegate_timeout"] = int(data["delegate_timeout"])
    if "intervention_enabled" in data:
        kwargs["intervention_enabled"] = bool(data["intervention_enabled"])
    if "brainstorm_participants" in data:
        kwargs["brainstorm_participants"] = data["brainstorm_participants"]

    return TriadConfig(**kwargs)
