"""Account diagnostics snapshot for Triad managed profiles."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from triad.core.accounts.manager import AccountManager
from triad.core.config import TriadConfig
from triad.core.provider_sessions import (
    provider_has_logged_in_session,
    provider_login_command,
    provider_source_dir,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_account_diagnostics_snapshot(
    config: TriadConfig,
    manager: AccountManager,
) -> dict[str, Any]:
    providers_payload: dict[str, dict[str, Any]] = {}

    for provider in config.providers_priority:
        pool = manager.pool_status(provider)
        source_dir = provider_source_dir(provider)
        providers_payload[provider] = {
            "provider": provider,
            "login_command": provider_login_command(provider),
            "source_session_dir": str(source_dir) if source_dir is not None else None,
            "source_session_available": provider_has_logged_in_session(provider),
            "managed_profile_count": len(pool),
            "available_profile_count": sum(1 for item in pool if item["available"]),
            "cooldown_profile_count": sum(
                1 for item in pool if item["cooldown_remaining_sec"] > 0
            ),
            "profiles": pool,
        }

    return {
        "recorded_at": _utcnow_iso(),
        "providers_priority": list(config.providers_priority),
        "providers": providers_payload,
    }
