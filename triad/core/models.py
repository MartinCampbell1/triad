"""Core data models for Triad."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IssueSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Profile:
    """One CLI account/profile."""

    name: str
    provider: str
    path: str
    is_available: bool = True
    requests_made: int = 0
    last_used: float = 0.0
    cooldown_until: float = 0.0
    consecutive_errors: int = 0

    def mark_rate_limited(self, cooldown_base: int = 300) -> None:
        self.is_available = False
        self.consecutive_errors += 1
        backoff = min(self.consecutive_errors * 60, 1800)
        self.cooldown_until = time.time() + cooldown_base + backoff

    def mark_success(self) -> None:
        self.consecutive_errors = 0
        self.is_available = True

    def check_available(self) -> bool:
        if not self.is_available and time.time() >= self.cooldown_until:
            self.is_available = True
            self.consecutive_errors = 0
        return self.is_available


@dataclass
class CriticIssue:
    """One issue found by a critic."""

    id: str
    severity: IssueSeverity
    kind: str
    file: str
    line: int | None = None
    summary: str = ""
    suggested_fix: str = ""


@dataclass
class CriticReport:
    """Structured output from a critic review."""

    status: str
    issues: list[CriticIssue] = field(default_factory=list)
    lgtm: bool = False
    raw_text: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "issues": [
                {
                    "id": issue.id,
                    "severity": issue.severity.value,
                    "kind": issue.kind,
                    "file": issue.file,
                    "line": issue.line,
                    "summary": issue.summary,
                    "suggested_fix": issue.suggested_fix,
                }
                for issue in self.issues
            ],
            "lgtm": self.lgtm,
        }
