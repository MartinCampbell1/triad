import pytest
import json
from pathlib import Path
from triad.core.modes.critic import CriticMode, CriticConfig
from triad.core.models import CriticReport, CriticIssue, IssueSeverity


def test_critic_config_defaults():
    cfg = CriticConfig(writer_provider="claude", critic_provider="codex")
    assert cfg.max_rounds == 5
    assert cfg.writer_provider == "claude"
    assert cfg.critic_provider == "codex"


def test_parse_critic_report_json():
    raw = json.dumps({
        "status": "needs_work",
        "issues": [{"id": "a1", "severity": "high", "kind": "security", "file": "auth.py", "summary": "bad"}],
        "lgtm": False,
    })
    report = CriticMode.parse_critic_output(raw)
    assert report.lgtm is False
    assert len(report.issues) == 1
    assert report.issues[0].severity == IssueSeverity.HIGH


def test_parse_critic_report_json_in_markdown_block():
    raw = '''Here is my review:
```json
{"status": "lgtm", "issues": [], "lgtm": true}
```
Overall good work.'''
    report = CriticMode.parse_critic_output(raw)
    assert report.lgtm is True
    assert len(report.issues) == 0


def test_parse_critic_report_fallback_lgtm_text():
    raw = "Looks good to me, no issues found. LGTM."
    report = CriticMode.parse_critic_output(raw)
    assert report.lgtm is True
    assert report.raw_text == raw


def test_parse_critic_report_fallback_issues_text():
    raw = "Found 2 issues:\n1. Missing error handling\n2. No tests"
    report = CriticMode.parse_critic_output(raw)
    assert report.lgtm is False
    assert report.raw_text == raw
