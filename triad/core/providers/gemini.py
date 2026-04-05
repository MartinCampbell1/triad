"""Gemini CLI adapter."""
from __future__ import annotations
from collections.abc import Mapping
from pathlib import Path
from triad.core.env import build_runtime_base_env
from triad.core.models import Profile
from triad.core.providers.base import ProviderAdapter


class GeminiAdapter(ProviderAdapter):
    provider = "gemini"
    cli_name = "gemini"

    def headless_command(self, prompt: str, **kwargs) -> list[str]:
        return ["gemini", "-p", prompt]

    def build_env(self, profile: Profile, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
        env = build_runtime_base_env(base_env)
        home = Path(profile.path) / "home"
        env["HOME"] = str(home)
        existing_path = env.get("PATH", "")
        homebrew = "/opt/homebrew/bin:/opt/homebrew/sbin"
        env["PATH"] = f"{homebrew}:{existing_path}"
        return env
