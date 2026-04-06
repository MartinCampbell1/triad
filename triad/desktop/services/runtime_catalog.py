from __future__ import annotations

from typing import Any

_MODE_CATALOG: list[dict[str, Any]] = [
    {
        "id": "solo",
        "label": "Solo",
        "description": "Single-provider interactive work.",
    },
    {
        "id": "critic",
        "label": "Critic",
        "description": "Writer/critic review loop with isolated worktree.",
    },
    {
        "id": "brainstorm",
        "label": "Brainstorm",
        "description": "Multi-provider ideation and synthesis.",
    },
    {
        "id": "delegate",
        "label": "Delegate",
        "description": "Parallel work lanes with provider isolation.",
    },
]

_MODEL_CATALOG: list[dict[str, Any]] = [
    {
        "id": "claude-opus-4-6",
        "label": "Claude Opus 4.6",
        "provider": "claude",
        "description": "High-capacity Claude model.",
    },
    {
        "id": "claude-sonnet-4-6",
        "label": "Claude Sonnet 4.6",
        "provider": "claude",
        "description": "Balanced Claude model.",
    },
    {
        "id": "gpt-5.4",
        "label": "GPT-5.4",
        "provider": "codex",
        "description": "Codex-compatible GPT model.",
    },
    {
        "id": "gpt-5.4-mini",
        "label": "GPT-5.4 Mini",
        "provider": "codex",
        "description": "Faster Codex-compatible GPT model.",
    },
    {
        "id": "gemini-2.5-pro",
        "label": "Gemini 2.5 Pro",
        "provider": "gemini",
        "description": "Gemini reasoning model.",
    },
    {
        "id": "gemini-2.5-flash",
        "label": "Gemini 2.5 Flash",
        "provider": "gemini",
        "description": "Faster Gemini model.",
    },
]

_PROVIDER_LABELS = {
    "claude": "Claude",
    "codex": "Codex",
    "gemini": "Gemini",
}


async def list_modes() -> list[dict[str, Any]]:
    return [dict(mode) for mode in _MODE_CATALOG]


async def list_models(provider: str | None = None) -> list[dict[str, Any]]:
    if provider:
        return [dict(model) for model in _MODEL_CATALOG if model["provider"] == provider]
    return [dict(model) for model in _MODEL_CATALOG]


async def list_capabilities(runtime: Any, provider: str | None = None, mode: str | None = None) -> dict[str, Any]:
    registry = getattr(runtime, "_capabilities", None)
    provider_names = [provider] if provider else list(registry.providers()) if registry is not None else []
    mode_names = [mode] if mode else ["interactive", "headless"]
    providers: list[dict[str, Any]] = []
    for provider_name in provider_names:
        surfaces: list[dict[str, Any]] = []
        for mode_name in mode_names:
            capabilities = []
            if registry is not None:
                capabilities = sorted(registry.get_capabilities(provider_name, mode_name))
            if capabilities:
                surfaces.append(
                    {
                        "mode": mode_name,
                        "capabilities": capabilities,
                    }
                )
        providers.append(
            {
                "id": provider_name,
                "label": _PROVIDER_LABELS.get(provider_name, provider_name.title()),
                "surfaces": surfaces,
            }
        )

    return {
        "providers": providers,
        "models": await list_models(provider),
        "modes": await list_modes(),
        "defaults": {
            "provider": "claude",
            "model": "claude-opus-4-6",
            "mode": "solo",
        },
    }
