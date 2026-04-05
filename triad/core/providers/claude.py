"""Claude Code CLI adapter."""
from __future__ import annotations
from collections.abc import Mapping
from pathlib import Path
from triad.core.env import build_runtime_base_env
from triad.core.models import Profile
from triad.core.providers.base import ProviderAdapter


class ClaudeAdapter(ProviderAdapter):
    provider = "claude"
    cli_name = "claude"

    def headless_command(self, prompt: str, session_id: str | None = None, policy: "ExecutionPolicy | None" = None, **kwargs) -> list[str]:
        from triad.core.execution_policy import ExecutionPolicy
        cmd = ["claude", "-p", prompt, "--output-format", "stream-json"]
        if session_id:
            cmd.extend(["--resume", session_id])
        if policy and policy.sandbox == "read_only":
            cmd.extend(["--permission-mode", "bypassPermissions", "--allowedTools", "Read,Grep,Glob,Bash(git diff *),Bash(git status *),Bash(git log *)"])
        return cmd

    def interactive_command(self) -> list[str]:
        return ["claude"]

    def build_env(self, profile: Profile, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
        env = build_runtime_base_env(base_env)
        home = Path(profile.path) / "home"
        env["HOME"] = str(home)
        existing_path = env.get("PATH", "")
        local_bin = str(home / ".local" / "bin")
        homebrew = "/opt/homebrew/bin:/opt/homebrew/sbin"
        env["PATH"] = f"{local_bin}:{homebrew}:{existing_path}"
        return env
