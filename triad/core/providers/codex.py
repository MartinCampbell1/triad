"""Codex CLI adapter."""
from __future__ import annotations
from collections.abc import Mapping
from triad.core.env import build_runtime_base_env
from triad.core.models import Profile
from triad.core.providers.base import ProviderAdapter


class CodexAdapter(ProviderAdapter):
    provider = "codex"
    cli_name = "codex"

    def headless_command(self, prompt: str, model: str | None = None, policy: "ExecutionPolicy | None" = None, **kwargs) -> list[str]:
        from triad.core.execution_policy import ExecutionPolicy
        if policy and policy.sandbox == "read_only":
            cmd = ["codex", "exec", "--sandbox", "read-only"]
        else:
            cmd = ["codex", "exec", "--full-auto"]
        if model:
            cmd.extend(["-m", model])
        cmd.append(prompt)
        return cmd

    def profile_is_valid(self, profile_dir) -> bool:
        return (profile_dir / "auth.json").exists() or (profile_dir / "config.toml").exists()

    def build_env(self, profile: Profile, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
        env = build_runtime_base_env(base_env)
        env["CODEX_HOME"] = str(profile.path)
        return env
