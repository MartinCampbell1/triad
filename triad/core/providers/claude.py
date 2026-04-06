"""Claude Code CLI adapter."""
from __future__ import annotations
import json
from collections.abc import Mapping
from pathlib import Path
from triad.core.env import build_runtime_base_env
from triad.core.models import Profile
from triad.core.providers.base import ProviderAdapter, StreamEvent


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

    def profile_is_valid(self, profile_dir) -> bool:
        return (profile_dir / "home" / ".claude").exists()

    def parse_stream_line(self, line: str) -> list[StreamEvent]:
        """Parse Claude's stream-json output into text/error events."""
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return super().parse_stream_line(line)

        if not isinstance(payload, dict):
            return []

        payload_type = payload.get("type")
        if payload_type == "error":
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message") or error.get("text")
            else:
                message = payload.get("message") or str(error or line)
            return [StreamEvent(kind="error", text=message)]

        texts: list[str] = []
        self._collect_stream_text(payload, texts)
        return [StreamEvent(kind="text", text=text) for text in texts if text]

    @classmethod
    def _collect_stream_text(cls, node, texts: list[str]) -> None:
        if isinstance(node, dict):
            text = node.get("text")
            if isinstance(text, str) and text:
                texts.append(text)
            for key in ("delta", "content", "message", "result"):
                if key in node:
                    cls._collect_stream_text(node[key], texts)
        elif isinstance(node, list):
            for item in node:
                cls._collect_stream_text(item, texts)

    def build_env(self, profile: Profile, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
        env = build_runtime_base_env(base_env)
        home = Path(profile.path) / "home"
        env["HOME"] = str(home)
        existing_path = env.get("PATH", "")
        local_bin = str(home / ".local" / "bin")
        homebrew = "/opt/homebrew/bin:/opt/homebrew/sbin"
        env["PATH"] = f"{local_bin}:{homebrew}:{existing_path}"
        return env
