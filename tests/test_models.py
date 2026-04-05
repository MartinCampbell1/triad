import time
from triad.core.models import Profile


def test_profile_creation():
    p = Profile(name="acc1", provider="codex", path="/tmp/codex/acc1")
    assert p.name == "acc1"
    assert p.provider == "codex"
    assert p.is_available is True
    assert p.consecutive_errors == 0


def test_profile_mark_rate_limited():
    p = Profile(name="acc1", provider="codex", path="/tmp/codex/acc1")
    p.mark_rate_limited(cooldown_base=10)
    assert p.is_available is False
    assert p.consecutive_errors == 1
    assert p.cooldown_until > time.time()


def test_profile_mark_rate_limited_exponential_backoff():
    p = Profile(name="acc1", provider="codex", path="/tmp/codex/acc1")
    p.mark_rate_limited(cooldown_base=10)
    first_cooldown = p.cooldown_until
    p.mark_rate_limited(cooldown_base=10)
    assert p.consecutive_errors == 2
    assert p.cooldown_until > first_cooldown


def test_profile_mark_success_resets_errors():
    p = Profile(name="acc1", provider="codex", path="/tmp/codex/acc1")
    p.mark_rate_limited(cooldown_base=10)
    p.mark_success()
    assert p.consecutive_errors == 0


def test_profile_check_available_after_cooldown():
    p = Profile(name="acc1", provider="codex", path="/tmp/codex/acc1")
    p.is_available = False
    p.cooldown_until = time.time() - 1
    assert p.check_available() is True
    assert p.is_available is True


def test_profile_check_available_during_cooldown():
    p = Profile(name="acc1", provider="codex", path="/tmp/codex/acc1")
    p.is_available = False
    p.cooldown_until = time.time() + 9999
    assert p.check_available() is False
