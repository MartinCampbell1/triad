"""Account manager — profile discovery, round-robin rotation, cooldowns."""
from __future__ import annotations

import time
from collections.abc import Mapping
from pathlib import Path

from triad.core.models import Profile
from triad.core.providers import get_adapter

_PROFILE_VALIDATORS: dict[str, list[str]] = {
    "claude": ["home/.claude"],
    "codex": ["auth.json"],
    "gemini": ["home/.config/gemini"],
}


def _profile_is_valid(provider: str, profile_dir: Path) -> bool:
    required_paths = _PROFILE_VALIDATORS.get(provider, [])
    return all((profile_dir / rp).exists() for rp in required_paths)


class AccountManager:
    def __init__(self, profiles_dir: Path, cooldown_base: int = 300):
        self.profiles_dir = profiles_dir
        self.cooldown_base = cooldown_base
        self.pools: dict[str, list[Profile]] = {}
        self._indexes: dict[str, int] = {}

    def discover(self) -> None:
        self.pools.clear()
        self._indexes.clear()
        for provider in ("claude", "codex", "gemini"):
            provider_dir = self.profiles_dir / provider
            if not provider_dir.exists():
                continue
            adapter = get_adapter(provider)
            profiles: list[Profile] = []
            for account_dir in sorted(provider_dir.iterdir()):
                if not account_dir.is_dir() or not account_dir.name.startswith("acc"):
                    continue
                if not adapter.profile_is_valid(account_dir):
                    continue
                profiles.append(
                    Profile(name=account_dir.name, provider=provider, path=str(account_dir))
                )
            if profiles:
                self.pools[provider] = profiles
                self._indexes[provider] = 0

    def get_next(self, provider: str, preferred_name: str | None = None) -> Profile | None:
        profiles = self.pools.get(provider, [])
        if not profiles:
            return None

        if preferred_name:
            for idx, profile in enumerate(profiles):
                if profile.name != preferred_name:
                    continue
                profile.check_available()
                if not profile.is_available:
                    return None
                self._indexes[provider] = (idx + 1) % len(profiles)
                profile.last_used = time.time()
                profile.requests_made += 1
                return profile
            return None

        start_idx = self._indexes.get(provider, 0)
        for offset in range(len(profiles)):
            idx = (start_idx + offset) % len(profiles)
            profile = profiles[idx]
            profile.check_available()
            if profile.is_available:
                self._indexes[provider] = (idx + 1) % len(profiles)
                profile.last_used = time.time()
                profile.requests_made += 1
                return profile
        return None

    def mark_rate_limited(self, provider: str, profile_name: str) -> None:
        for profile in self.pools.get(provider, []):
            if profile.name == profile_name:
                profile.mark_rate_limited(self.cooldown_base)
                return

    def mark_success(self, provider: str, profile_name: str) -> None:
        for profile in self.pools.get(provider, []):
            if profile.name == profile_name:
                profile.mark_success()
                return

    def pool_status(self, provider: str) -> list[dict]:
        now = time.time()
        return [
            {
                "name": profile.name,
                "available": profile.is_available or now >= profile.cooldown_until,
                "requests_made": profile.requests_made,
                "errors": profile.consecutive_errors,
                "cooldown_remaining_sec": (
                    max(0, round(profile.cooldown_until - now))
                    if not profile.is_available and now < profile.cooldown_until
                    else 0
                ),
            }
            for profile in self.pools.get(provider, [])
        ]

    def build_env(
        self,
        profile: Profile,
        base_env: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        return get_adapter(profile.provider).build_env(profile, base_env)

    def status(self) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}
        for provider, profiles in self.pools.items():
            result[provider] = [
                {"name": p.name, "available": p.check_available(), "requests": p.requests_made, "errors": p.consecutive_errors}
                for p in profiles
            ]
        return result
