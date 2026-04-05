"""PolicyGuard — safety checks before launching providers."""
from __future__ import annotations

from collections.abc import Mapping

_DANGEROUS_KEYS = {
    "ANTHROPIC_API_KEY": "Claude will use API billing instead of subscription. Remove to use Max plan.",
    "OPENAI_API_KEY": "Codex may use API billing. Ensure this is intentional.",
}


class PolicyGuard:
    def check_environment(self, env: Mapping[str, str]) -> list[str]:
        warnings: list[str] = []
        for key, msg in _DANGEROUS_KEYS.items():
            if key in env and env[key]:
                warnings.append(f"WARNING: {key} is set. {msg}")
        return warnings
