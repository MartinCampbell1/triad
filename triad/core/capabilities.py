"""Provider capability registry — honest matrix of what works where."""
from __future__ import annotations

_MATRIX: dict[str, dict[str, set[str]]] = {
    "claude": {
        "interactive": {
            "full_tui", "stream_json", "resume", "mcp", "hooks",
            "skills", "plugins", "computer_use", "ask_user", "superpowers",
            "worktree",
        },
        "headless": {
            "stream_json", "resume", "mcp", "hooks", "skills",
            "plugins", "worktree", "exec",
        },
    },
    "codex": {
        "headless": {
            "exec", "review", "model_override",
        },
    },
    "gemini": {
        "headless": {
            "exec",
        },
    },
}


class CapabilityRegistry:
    def supports(self, provider: str, mode: str, capability: str) -> bool:
        provider_caps = _MATRIX.get(provider)
        if provider_caps is None:
            return False
        mode_caps = provider_caps.get(mode)
        if mode_caps is None:
            return False
        return capability in mode_caps

    def get_capabilities(self, provider: str, mode: str) -> set[str]:
        return _MATRIX.get(provider, {}).get(mode, set())

    def providers(self) -> list[str]:
        return list(_MATRIX.keys())
