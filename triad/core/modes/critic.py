"""Critic mode — iterative writer + critic loop with structured review."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from triad.core.context.blackboard import Blackboard
from triad.core.models import CriticIssue, CriticReport, IssueSeverity, Profile
from triad.core.modes.base import ModeState
from triad.core.providers.base import ProviderAdapter
from triad.core.storage.ledger import Ledger

_WRITER_PROMPT = """You are implementing code for a task. Use your full capabilities.

{blackboard_context}

{critic_feedback}

Implement the changes. Be thorough. Write actual code, not descriptions."""

_CRITIC_PROMPT = """You are a thorough code reviewer. Be specific and actionable.

## Original Task
{task}

## Code Written
{writer_output}

Review the code. Output your review as JSON:
{{"status": "needs_work" or "lgtm", "issues": [{{"id": "...", "severity": "critical|high|medium|low", "kind": "security|correctness|performance|style", "file": "...", "summary": "...", "suggested_fix": "..."}}], "lgtm": true or false}}

If no issues, set lgtm to true and issues to []."""


@dataclass
class CriticConfig:
    writer_provider: str
    critic_provider: str
    max_rounds: int = 5
    workdir: Path = field(default_factory=lambda: Path.cwd())


@dataclass
class RoundResult:
    round_number: int
    writer_output: str
    critic_report: CriticReport
    writer_provider: str
    critic_provider: str


class CriticMode:
    def __init__(
        self,
        config: CriticConfig,
        writer_adapter: ProviderAdapter,
        critic_adapter: ProviderAdapter,
        writer_profile: Profile,
        critic_profile: Profile,
        ledger: Ledger,
        blackboard: Blackboard,
    ):
        self.config = config
        self.writer_adapter = writer_adapter
        self.critic_adapter = critic_adapter
        self.writer_profile = writer_profile
        self.critic_profile = critic_profile
        self.ledger = ledger
        self.blackboard = blackboard
        self.state = ModeState.IDLE
        self.session_id: str | None = None
        self._writer_session_id: str | None = None
        self._rounds: list[RoundResult] = []

    async def initialize(self) -> str:
        self.session_id = await self.ledger.create_session(
            mode="critic",
            task=self.blackboard.task,
            config_json=json.dumps({
                "writer": self.config.writer_provider,
                "critic": self.config.critic_provider,
                "max_rounds": self.config.max_rounds,
            }),
        )
        self.state = ModeState.RUNNING
        return self.session_id

    async def run_round(self, user_feedback: str | None = None) -> RoundResult:
        round_num = len(self._rounds) + 1

        blackboard_context = self.blackboard.render_for_role("writer")
        critic_feedback = ""
        if self._rounds:
            last = self._rounds[-1]
            if last.critic_report.issues:
                issues_text = "\n".join(
                    f"- [{i.severity}] {i.file}: {i.summary}"
                    for i in last.critic_report.issues
                )
                critic_feedback = f"## Previous Critic Findings\n{issues_text}"
        if user_feedback:
            critic_feedback += f"\n\n## User Feedback\n{user_feedback}"

        writer_prompt = _WRITER_PROMPT.format(
            blackboard_context=blackboard_context,
            critic_feedback=critic_feedback,
        )

        await self.ledger.log_event(
            self.session_id, "provider.started",
            agent=f"{self.config.writer_provider}/writer",
        )
        writer_result = await self.writer_adapter.execute(
            profile=self.writer_profile,
            prompt=writer_prompt,
            workdir=self.config.workdir,
            session_id=self._writer_session_id,
        )
        writer_output = writer_result.stdout
        await self.ledger.log_event(
            self.session_id, "provider.finished",
            agent=f"{self.config.writer_provider}/writer",
            content=writer_output[:2000],
        )

        critic_prompt = _CRITIC_PROMPT.format(
            task=self.blackboard.task,
            writer_output=writer_output[:8000],
        )
        await self.ledger.log_event(
            self.session_id, "provider.started",
            agent=f"{self.config.critic_provider}/critic",
        )
        critic_result = await self.critic_adapter.execute(
            profile=self.critic_profile,
            prompt=critic_prompt,
            workdir=self.config.workdir,
        )
        critic_output = critic_result.stdout
        await self.ledger.log_event(
            self.session_id, "provider.finished",
            agent=f"{self.config.critic_provider}/critic",
            content=critic_output[:2000],
        )

        report = self.parse_critic_output(critic_output)

        writer_aid = await self.ledger.store_artifact(
            self.session_id, kind="writer_output", content=writer_output,
        )
        critic_aid = await self.ledger.store_artifact(
            self.session_id, kind="critic_report",
            content=json.dumps(report.to_dict()),
        )
        self.blackboard.add_artifact("writer_diff", writer_aid)
        self.blackboard.add_artifact("critic_report", critic_aid)

        round_result = RoundResult(
            round_number=round_num,
            writer_output=writer_output,
            critic_report=report,
            writer_provider=self.config.writer_provider,
            critic_provider=self.config.critic_provider,
        )
        self._rounds.append(round_result)

        if report.lgtm or round_num >= self.config.max_rounds:
            self.state = ModeState.COMPLETED
            await self.ledger.update_session_status(self.session_id, "completed")
        else:
            self.state = ModeState.INTERVENTION

        return round_result

    @property
    def rounds(self) -> list[RoundResult]:
        return list(self._rounds)

    def swap_roles(self) -> None:
        """Swap writer and critic — adapters, profiles, and config."""
        self.writer_adapter, self.critic_adapter = self.critic_adapter, self.writer_adapter
        self.writer_profile, self.critic_profile = self.critic_profile, self.writer_profile
        self.config.writer_provider, self.config.critic_provider = (
            self.config.critic_provider,
            self.config.writer_provider,
        )

    @staticmethod
    def parse_critic_output(raw: str) -> CriticReport:
        # Try parsing the entire string as JSON first
        stripped = raw.strip()
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
                if isinstance(data, dict) and any(
                    k in data for k in ("status", "lgtm", "issues")
                ):
                    return CriticMode._report_from_json(data, raw)
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        # Try markdown ```json block
        json_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if json_block:
            try:
                data = json.loads(json_block.group(1))
                return CriticMode._report_from_json(data, raw)
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        # Fallback: text heuristics
        lower = raw.lower()
        is_lgtm = any(
            p in lower for p in ("lgtm", "looks good", "no issues", "approved")
        )
        return CriticReport(
            status="lgtm" if is_lgtm else "needs_work",
            issues=[],
            lgtm=is_lgtm,
            raw_text=raw,
        )

    @staticmethod
    def _report_from_json(data: dict, raw: str) -> CriticReport:
        issues = []
        for item in data.get("issues", []):
            issues.append(CriticIssue(
                id=item.get("id", ""),
                severity=IssueSeverity(item.get("severity", "medium")),
                kind=item.get("kind", ""),
                file=item.get("file", ""),
                line=item.get("line"),
                summary=item.get("summary", ""),
                suggested_fix=item.get("suggested_fix", ""),
            ))
        return CriticReport(
            status=data.get("status", "needs_work"),
            issues=issues,
            lgtm=data.get("lgtm", False),
            raw_text=raw,
        )
