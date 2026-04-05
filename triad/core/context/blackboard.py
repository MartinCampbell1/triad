"""Shared working memory — the current 'picture of reality' for orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Blackboard:
    task: str = ""
    current_plan: list[str] = field(default_factory=list)
    open_issues: list[str] = field(default_factory=list)
    latest_artifacts: dict[str, str] = field(default_factory=dict)
    decisions_made: list[str] = field(default_factory=list)
    accepted_constraints: list[str] = field(default_factory=list)

    def add_artifact(self, key: str, artifact_id: str) -> None:
        self.latest_artifacts[key] = artifact_id

    def add_decision(self, decision: str) -> None:
        self.decisions_made.append(decision)

    def render_for_role(self, role: str) -> str:
        sections: list[str] = []
        sections.append(f"## Task\n{self.task}")
        if self.current_plan:
            plan_text = "\n".join(f"- {s}" for s in self.current_plan)
            sections.append(f"## Current Plan\n{plan_text}")
        if self.accepted_constraints:
            constraints = "\n".join(f"- {c}" for c in self.accepted_constraints)
            sections.append(f"## Constraints\n{constraints}")
        if role == "writer" and self.open_issues:
            issues = "\n".join(f"- {i}" for i in self.open_issues)
            sections.append(f"## Open Issues\n{issues}")
        if self.decisions_made:
            decisions = "\n".join(f"- {d}" for d in self.decisions_made)
            sections.append(f"## Decisions Made\n{decisions}")
        return "\n\n".join(sections)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "current_plan": self.current_plan,
            "open_issues": self.open_issues,
            "latest_artifacts": self.latest_artifacts,
            "decisions_made": self.decisions_made,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Blackboard:
        return cls(
            task=data.get("task", ""),
            current_plan=data.get("current_plan", []),
            open_issues=data.get("open_issues", []),
            latest_artifacts=data.get("latest_artifacts", {}),
            decisions_made=data.get("decisions_made", []),
        )
