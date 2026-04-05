"""Configuration management — YAML config at ~/.triad/config.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class TriadConfig:
    """Triad configuration."""

    # Defaults
    default_mode: str = "critic"
    default_writer: str = "claude"
    default_critic: str = "codex"

    # Paths
    profiles_dir: Path = field(default_factory=lambda: Path.home() / ".cli-profiles")
    triad_home: Path = field(default_factory=lambda: Path.home() / ".triad")

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
