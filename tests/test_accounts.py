from pathlib import Path
from triad.core.accounts.manager import AccountManager


def test_discover_finds_profiles(tmp_profiles: Path):
    mgr = AccountManager(profiles_dir=tmp_profiles)
    mgr.discover()
    assert "claude" in mgr.pools
    assert len(mgr.pools["claude"]) == 1
    assert "codex" in mgr.pools
    assert len(mgr.pools["codex"]) == 3
    assert "gemini" in mgr.pools
    assert len(mgr.pools["gemini"]) == 2


def test_get_next_returns_profile(tmp_profiles: Path):
    mgr = AccountManager(profiles_dir=tmp_profiles)
    mgr.discover()
    profile = mgr.get_next("codex")
    assert profile is not None
    assert profile.provider == "codex"
    assert profile.name == "acc1"


def test_get_next_round_robin(tmp_profiles: Path):
    mgr = AccountManager(profiles_dir=tmp_profiles)
    mgr.discover()
    p1 = mgr.get_next("codex")
    p2 = mgr.get_next("codex")
    p3 = mgr.get_next("codex")
    assert p1.name == "acc1"
    assert p2.name == "acc2"
    assert p3.name == "acc3"


def test_get_next_skips_rate_limited(tmp_profiles: Path):
    mgr = AccountManager(profiles_dir=tmp_profiles)
    mgr.discover()
    mgr.mark_rate_limited("codex", "acc1")
    p = mgr.get_next("codex")
    assert p is not None
    assert p.name == "acc2"


def test_get_next_returns_none_all_exhausted(tmp_profiles: Path):
    mgr = AccountManager(profiles_dir=tmp_profiles)
    mgr.discover()
    for profile in mgr.pools["codex"]:
        profile.is_available = False
        profile.cooldown_until = 9999999999.0
    assert mgr.get_next("codex") is None


def test_get_next_unknown_provider(tmp_profiles: Path):
    mgr = AccountManager(profiles_dir=tmp_profiles)
    mgr.discover()
    assert mgr.get_next("unknown") is None


def test_mark_success(tmp_profiles: Path):
    mgr = AccountManager(profiles_dir=tmp_profiles)
    mgr.discover()
    mgr.mark_rate_limited("codex", "acc1")
    profile = mgr.pools["codex"][0]
    assert profile.consecutive_errors == 1
    mgr.mark_success("codex", "acc1")
    assert profile.consecutive_errors == 0
