from triad.core.providers.claude import ClaudeAdapter
from triad.core.providers.codex import CodexAdapter
from triad.core.providers.gemini import GeminiAdapter

ADAPTERS: dict[str, type] = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "gemini": GeminiAdapter,
}


def get_adapter(provider: str):
    cls = ADAPTERS.get(provider)
    if cls is None:
        raise ValueError(f"Unknown provider: {provider}")
    return cls()
