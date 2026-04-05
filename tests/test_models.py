import time
from triad.core.models import Profile, CriticReport, CriticIssue, IssueSeverity


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


def test_mark_success_restores_available():
    p = Profile(name="acc1", provider="codex", path="/tmp/codex/acc1")
    p.mark_rate_limited(cooldown_base=10)
    assert p.is_available is False
    p.mark_success()
    assert p.is_available is True


def test_critic_report_to_dict():
    report = CriticReport(
        status="needs_work",
        issues=[
            CriticIssue(id="a1", severity=IssueSeverity.HIGH, kind="security", file="auth.py", summary="bad token handling")
        ],
        lgtm=False,
    )
    d = report.to_dict()
    assert d["status"] == "needs_work"
    assert d["lgtm"] is False
    assert len(d["issues"]) == 1
    assert d["issues"][0]["severity"] == "high"


def test_critic_report_lgtm():
    report = CriticReport(status="lgtm", lgtm=True)
    d = report.to_dict()
    assert d["lgtm"] is True
    assert d["issues"] == []
