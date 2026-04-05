"""Runtime environment sanitization for CLI subprocess invocations."""
from __future__ import annotations

import os
from collections.abc import Mapping

RUNTIME_ENV_EXACT_ALLOWLIST: frozenset[str] = frozenset({
    "PATH", "HOME", "SHELL", "TERM", "LANG", "LC_ALL", "LC_CTYPE",
    "LC_COLLATE", "LC_MESSAGES", "TZ", "TMPDIR", "TMP", "TEMP",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE", "NO_COLOR", "COLORTERM", "CI",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "NVM_DIR", "NVM_BIN",
})

RUNTIME_ENV_PREFIX_ALLOWLIST: tuple[str, ...] = (
    "TRIAD_", "CODEX_", "CLAUDE_", "OPENAI_", "ANTHROPIC_",
    "GOOGLE_", "GEMINI_",
)


def runtime_env_key_allowed(key: str) -> bool:
    """Return whether an inherited environment key is safe to forward."""
    normalized = str(key or "").strip()
    if not normalized:
        return False
    if normalized in RUNTIME_ENV_EXACT_ALLOWLIST:
        return True
    return any(normalized.startswith(prefix) for prefix in RUNTIME_ENV_PREFIX_ALLOWLIST)


def build_runtime_base_env(base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a sanitized runtime env containing only safe inherited keys."""
    source = dict(base_env) if base_env is not None else dict(os.environ)
    sanitized = {
        str(k): str(v)
        for k, v in source.items()
        if runtime_env_key_allowed(str(k))
    }
    sanitized.setdefault("PATH", str(source.get("PATH") or os.defpath))
    return sanitized
