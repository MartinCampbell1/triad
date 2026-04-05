"""PolicyGuard — safety checks before launching providers."""
from __future__ import annotations

from collections.abc import Mapping
from triad.core.env import DANGEROUS_AUTH_KEYS

_DANGEROUS_KEY_WARNINGS = {
    "ANTHROPIC_API_KEY": "Claude will use API billing instead of subscription. Stripped by default.",
    "OPENAI_API_KEY": "Codex may use API billing. Stripped by default.",
    "GOOGLE_API_KEY": "Gemini may use API billing. Stripped by default.",
    "GEMINI_API_KEY": "Gemini may use API billing. Stripped by default.",
}


class PolicyGuard:
    def check_environment(self, env: Mapping[str, str]) -> list[str]:
        warnings: list[str] = []
        for key, msg in _DANGEROUS_KEY_WARNINGS.items():
            if key in env and env[key]:
                warnings.append(f"WARNING: {key} detected in shell environment. {msg}")
        return warnings
