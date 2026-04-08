"""Codex CLI adapter."""

from __future__ import annotations

import json
from collections.abc import Mapping

from triad.core.env import build_runtime_base_env
from triad.core.models import Profile
from triad.core.providers.base import ProviderAdapter, StreamEvent


class CodexAdapter(ProviderAdapter):
    provider = "codex"
    cli_name = "codex"

    def headless_command(
        self,
        prompt: str,
        model: str | None = None,
        policy: "ExecutionPolicy | None" = None,
        **kwargs,
    ) -> list[str]:
        from triad.core.execution_policy import ExecutionPolicy

        if policy and policy.sandbox == "read_only":
            cmd = ["codex", "exec", "--json", "--sandbox", "read-only"]
        else:
            cmd = ["codex", "exec", "--json", "--full-auto"]
        if model:
            cmd.extend(["-m", model])
        cmd.append(prompt)
        return cmd

    def parse_stream_line(self, line: str) -> list[StreamEvent]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return super().parse_stream_line(line)

        if not isinstance(payload, dict):
            return []

        event_type = str(payload.get("type") or "")
        if event_type in {"error", "run_error"}:
            message = payload.get("message") or payload.get("error") or line
            return [StreamEvent(kind="error", text=str(message))]

        if event_type in {"tool_started", "tool_start", "tool_use"}:
            return [
                StreamEvent(
                    kind="tool_use",
                    data={
                        "tool": str(
                            payload.get("tool") or payload.get("name") or "tool"
                        ),
                        "input": payload.get("input") or payload.get("args") or {},
                        "status": "running",
                    },
                )
            ]

        if event_type in {"tool_finished", "tool_result", "tool_end"}:
            success = payload.get("success")
            return [
                StreamEvent(
                    kind="tool_result",
                    data={
                        "tool": str(
                            payload.get("tool") or payload.get("name") or "tool"
                        ),
                        "input": payload.get("input") or payload.get("args") or {},
                        "output": payload.get("output") or payload.get("result"),
                        "status": "failed" if success is False else "completed",
                        "success": False if success is False else True,
                    },
                )
            ]

        texts: list[str] = []
        self._collect_stream_text(payload, texts)
        return [StreamEvent(kind="text", text=text) for text in texts if text]

    @classmethod
    def _collect_stream_text(cls, node: object, texts: list[str]) -> None:
        if isinstance(node, dict):
            for key in ("text", "delta", "content", "message", "result"):
                value = node.get(key)
                if isinstance(value, str) and value:
                    texts.append(value)
                elif isinstance(value, (dict, list)):
                    cls._collect_stream_text(value, texts)
        elif isinstance(node, list):
            for item in node:
                cls._collect_stream_text(item, texts)

    def profile_is_valid(self, profile_dir) -> bool:
        return (profile_dir / "auth.json").exists() or (
            profile_dir / "config.toml"
        ).exists()

    def build_env(
        self, profile: Profile, base_env: Mapping[str, str] | None = None
    ) -> dict[str, str]:
        env = build_runtime_base_env(base_env)
        env["CODEX_HOME"] = str(profile.path)
        return env
