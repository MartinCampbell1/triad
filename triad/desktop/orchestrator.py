"""Multi-agent orchestration engine for desktop client."""
from __future__ import annotations

import asyncio
import contextlib
import json
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from triad.core.accounts.manager import AccountManager
from triad.core.config import get_default_config_path, load_config
from triad.core.execution_policy import ExecutionPolicy
from triad.core.providers import get_adapter
from triad.core.providers.base import is_rate_limited
from triad.core.repo_artifacts import capture_repo_artifacts
from triad.core.worktrees import WorktreeManager

from .services.provider_streams import ProviderStreamRelay
from .services.run_lifecycle import (
    RunLifecycleContext,
    build_run_completed_event,
    build_run_failed_event,
    build_run_started_event,
)

UiEventHandler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(slots=True)
class CriticRound:
    round_number: int
    writer_provider: str
    critic_provider: str
    writer_output: str = ""
    critic_output: str = ""
    findings: list[dict[str, Any]] = field(default_factory=list)
    lgtm: bool = False


@dataclass(slots=True)
class BrainstormIdea:
    provider: str
    role: str
    content: str


@dataclass(slots=True)
class DelegateLane:
    provider: str
    role: str
    output: str = ""
    error: str | None = None
    success: bool = False
    worktree_path: Path | None = None


class Orchestrator:
    """Drives multi-agent modes: critic, brainstorm, delegate."""

    def __init__(
        self,
        on_event: UiEventHandler,
        *,
        account_manager: AccountManager | None = None,
        adapter_factory: Callable[[str], Any] | None = None,
        worktree_manager: WorktreeManager | None = None,
        use_critic_worktrees: bool = True,
        use_delegate_worktrees: bool = True,
    ) -> None:
        self.on_event = on_event
        self._adapter_factory = adapter_factory or get_adapter
        self._config = load_config(get_default_config_path())
        self._worktree_manager = worktree_manager or WorktreeManager(self._config.worktrees_dir)
        self._use_critic_worktrees = use_critic_worktrees
        self._use_delegate_worktrees = use_delegate_worktrees
        if account_manager is not None:
            self._account_mgr = account_manager
        else:
            self._account_mgr = AccountManager(
                profiles_dir=self._config.profiles_dir,
                cooldown_base=self._config.cooldown_base_sec,
            )
            self._account_mgr.discover()

    async def run_critic(
        self,
        *,
        session_id: str,
        prompt: str,
        workdir: Path,
        writer_provider: str,
        critic_provider: str,
        max_rounds: int = 3,
        writer_model: str | None = None,
        critic_model: str | None = None,
    ) -> list[CriticRound]:
        """Run a writer/critic loop and stream UI events for each phase."""
        rounds: list[CriticRound] = []
        critic_worktree: Path | None = None
        critic_workdir = workdir

        try:
            if self._use_critic_worktrees:
                if not self._is_git_repo(workdir):
                    raise RuntimeError(
                        f"Critic mode requires a git repository so it can use an isolated worktree: {workdir}"
                    )
                critic_worktree = self._worktree_manager.create(
                    repo_path=workdir,
                    name=f"desktop-critic-{session_id}",
                )
                critic_workdir = critic_worktree

            for round_number in range(1, max_rounds + 1):
                round_run_id = f"{session_id}:critic:{round_number}"
                await self.on_event(
                    {
                        "session_id": session_id,
                        "run_id": round_run_id,
                        "type": "system",
                        "provider": writer_provider,
                        "content": f"Critic round {round_number}/{max_rounds}",
                    }
                )

                writer_prompt = self._build_writer_prompt(prompt, rounds[-1].findings if rounds else None)
                writer_output = await self._run_actor(
                    session_id=session_id,
                    provider=writer_provider,
                    prompt=writer_prompt,
                    workdir=critic_workdir,
                    role="writer",
                    model=writer_model,
                    policy=ExecutionPolicy.writer(),
                    run_id=f"{round_run_id}:writer",
                    timeout=self._config.delegate_timeout,
                )

                repo_state = capture_repo_artifacts(critic_workdir)
                if repo_state.get("diff_patch") or repo_state.get("diff_stat"):
                    await self.on_event(
                        {
                            "session_id": session_id,
                            "run_id": round_run_id,
                            "type": "diff_snapshot",
                            "provider": writer_provider,
                            "role": "writer",
                            "patch": repo_state.get("diff_patch", ""),
                            "diff_stat": repo_state.get("diff_stat", ""),
                        }
                    )
                critic_prompt = self._build_critic_prompt(
                    task=prompt,
                    writer_output=writer_output,
                    repo_state=repo_state,
                )
                critic_output = await self._run_actor(
                    session_id=session_id,
                    provider=critic_provider,
                    prompt=critic_prompt,
                    workdir=critic_workdir,
                    role="critic",
                    model=critic_model,
                    policy=ExecutionPolicy.critic(),
                    run_id=f"{round_run_id}:critic",
                    timeout=self._config.delegate_timeout,
                )

                report = self._parse_critic_output(critic_output)
                findings = self._report_to_findings(report)
                round_result = CriticRound(
                    round_number=round_number,
                    writer_provider=writer_provider,
                    critic_provider=critic_provider,
                    writer_output=writer_output,
                    critic_output=critic_output,
                    findings=findings,
                    lgtm=report.lgtm and not findings,
                )
                rounds.append(round_result)

                for finding in findings:
                    await self.on_event(
                        {
                            "session_id": session_id,
                            "run_id": round_run_id,
                            "type": "review_finding",
                            "provider": critic_provider,
                            "role": "critic",
                            **finding,
                        }
                    )

                if round_result.lgtm:
                    await self.on_event(
                        {
                            "session_id": session_id,
                            "run_id": round_run_id,
                            "type": "system",
                            "provider": critic_provider,
                            "content": f"Critic approved in round {round_number}. LGTM",
                        }
                    )
                    break

            if rounds and not rounds[-1].lgtm:
                await self.on_event(
                    {
                        "session_id": session_id,
                        "run_id": f"{session_id}:critic",
                        "type": "system",
                        "provider": critic_provider,
                        "content": f"Critic stopped after {len(rounds)} rounds without LGTM.",
                    }
                )

            await self.on_event(
                {
                    "session_id": session_id,
                    "run_id": f"{session_id}:critic",
                    "type": "run_completed",
                    "provider": critic_provider,
                }
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.on_event(
                {
                    "session_id": session_id,
                    "run_id": f"{session_id}:critic",
                    "type": "run_failed",
                    "provider": critic_provider,
                    "error": str(exc),
                }
            )
        finally:
            if critic_worktree is not None:
                with contextlib.suppress(Exception):
                    self._worktree_manager.remove(critic_worktree)

        return rounds

    async def run_brainstorm(
        self,
        *,
        session_id: str,
        prompt: str,
        workdir: Path,
        ideator_providers: list[str],
        moderator_provider: str,
        ideator_model: str | None = None,
        moderator_model: str | None = None,
    ) -> list[BrainstormIdea]:
        ideas: list[BrainstormIdea] = []

        try:
            ordered_ideators = self._ordered_providers(ideator_providers)
            for index, provider in enumerate(ordered_ideators, start=1):
                run_id = f"{session_id}:brainstorm:idea:{index}"
                await self.on_event(
                    {
                        "session_id": session_id,
                        "run_id": run_id,
                        "type": "system",
                        "provider": provider,
                        "content": f"Ideation pass {index}/{len(ordered_ideators)}",
                    }
                )
                idea_text = await self._run_actor(
                    session_id=session_id,
                    provider=provider,
                    prompt=self._build_brainstorm_prompt(prompt, ideas, index),
                    workdir=workdir,
                    role="ideator",
                    model=ideator_model if provider == ordered_ideators[0] else None,
                    policy=ExecutionPolicy.critic(),
                    run_id=run_id,
                    timeout=self._config.delegate_timeout,
                )
                ideas.append(BrainstormIdea(provider=provider, role="ideator", content=idea_text))

            if not ideas:
                raise RuntimeError("No brainstorm outputs were produced")

            moderator_run_id = f"{session_id}:brainstorm:moderator"
            synthesis = await self._run_actor(
                session_id=session_id,
                provider=moderator_provider,
                prompt=self._build_moderator_prompt(prompt, ideas),
                workdir=workdir,
                role="moderator",
                model=moderator_model,
                policy=ExecutionPolicy.critic(),
                run_id=moderator_run_id,
                timeout=self._config.delegate_timeout,
            )
            ideas.append(BrainstormIdea(provider=moderator_provider, role="moderator", content=synthesis))

            await self.on_event(
                {
                    "session_id": session_id,
                    "run_id": f"{session_id}:brainstorm",
                    "type": "run_completed",
                    "provider": moderator_provider,
                }
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.on_event(
                {
                    "session_id": session_id,
                    "run_id": f"{session_id}:brainstorm",
                    "type": "run_failed",
                    "provider": moderator_provider,
                    "error": str(exc),
                }
            )

        return ideas

    async def run_delegate(
        self,
        *,
        session_id: str,
        prompt: str,
        workdir: Path,
        lane_providers: list[str],
        model: str | None = None,
    ) -> list[DelegateLane]:
        lanes = [
            DelegateLane(provider=provider, role="delegate")
            for provider in self._ordered_providers(lane_providers)
        ]

        async def run_lane(index: int, lane: DelegateLane) -> DelegateLane:
            run_id = f"{session_id}:delegate:{index}"
            lane_workdir = workdir
            try:
                if self._use_delegate_worktrees and len(lanes) > 1 and self._is_git_repo(workdir):
                    lane.worktree_path = self._worktree_manager.create(
                        repo_path=workdir,
                        name=f"desktop-delegate-{session_id}-{index}",
                    )
                    lane_workdir = lane.worktree_path
                await self.on_event(
                    {
                        "session_id": session_id,
                        "run_id": run_id,
                        "type": "system",
                        "provider": lane.provider,
                        "content": (
                            f"Delegate lane {index} started"
                            + (f" in {lane_workdir}" if lane.worktree_path else "")
                        ),
                    }
                )
                lane.output = await self._run_actor(
                    session_id=session_id,
                    provider=lane.provider,
                    prompt=self._build_delegate_prompt(prompt, index, lane.provider),
                    workdir=lane_workdir,
                    role=lane.role,
                    model=model if index == 1 else None,
                    policy=ExecutionPolicy.delegate(),
                    run_id=run_id,
                    stream=True,
                    timeout=self._config.delegate_timeout,
                )
                lane.success = True
                await self.on_event(
                    {
                        "session_id": session_id,
                        "run_id": run_id,
                        "type": "system",
                        "provider": lane.provider,
                        "content": f"Delegate lane {index} completed",
                    }
                )
            except Exception as exc:  # noqa: BLE001
                lane.error = str(exc)
                await self.on_event(
                    {
                        "session_id": session_id,
                        "run_id": run_id,
                        "type": "run_failed",
                        "provider": lane.provider,
                        "role": lane.role,
                        "error": f"Delegate lane {index} failed: {lane.error}",
                    }
                )
            finally:
                if lane.worktree_path is not None:
                    with contextlib.suppress(Exception):
                        self._worktree_manager.remove(lane.worktree_path)
            return lane

        try:
            if not lanes:
                raise RuntimeError("No delegate providers configured")

            results = await asyncio.gather(
                *(run_lane(index, lane) for index, lane in enumerate(lanes, start=1)),
                return_exceptions=False,
            )
            success_count = sum(1 for lane in results if lane.success)
            failure_count = sum(1 for lane in results if not lane.success)

            await self.on_event(
                {
                    "session_id": session_id,
                    "run_id": f"{session_id}:delegate",
                    "type": "system",
                    "provider": results[0].provider,
                    "content": f"Delegate finished: {success_count} completed, {failure_count} failed.",
                }
            )

            if success_count == 0:
                await self.on_event(
                    {
                        "session_id": session_id,
                        "run_id": f"{session_id}:delegate",
                        "type": "run_failed",
                        "provider": results[0].provider,
                        "error": "All delegate lanes failed",
                    }
                )
            else:
                await self.on_event(
                    {
                        "session_id": session_id,
                        "run_id": f"{session_id}:delegate",
                        "type": "run_completed",
                        "provider": results[0].provider,
                    }
                )
            return results
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.on_event(
                {
                    "session_id": session_id,
                    "run_id": f"{session_id}:delegate",
                    "type": "run_failed",
                    "provider": lanes[0].provider if lanes else None,
                    "error": str(exc),
                }
            )
            return lanes

    async def _run_actor(
        self,
        *,
        session_id: str,
        provider: str,
        prompt: str,
        workdir: Path,
        role: str,
        model: str | None = None,
        policy: ExecutionPolicy | None = None,
        run_id: str | None = None,
        stream: bool = True,
        timeout: int | None = None,
    ) -> str:
        adapter = self._adapter_factory(provider)
        profile = self._account_mgr.get_next(provider)
        if profile is None:
            raise RuntimeError(f"No available {provider} accounts")

        await self.on_event(
            build_run_started_event(
                RunLifecycleContext(
                    session_id=session_id,
                    run_id=run_id,
                    provider=provider,
                    role=role,
                    policy_role=policy.role if policy else None,
                    sandbox=policy.sandbox if policy else None,
                    workdir=workdir,
                )
            )
        )

        relay = ProviderStreamRelay(
            session_id=session_id,
            provider=provider,
            run_id=run_id,
            role=role,
            on_event=self.on_event,
            stream_text=stream,
        )
        try:
            outcome = await relay.consume(
                adapter.execute_stream(
                    profile=profile,
                    prompt=prompt,
                    workdir=workdir,
                    model=model,
                    policy=policy,
                    timeout=timeout or self._config.delegate_timeout,
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.on_event(
                build_run_failed_event(
                    RunLifecycleContext(
                        session_id=session_id,
                        run_id=run_id,
                        provider=provider,
                        role=role,
                        policy_role=policy.role if policy else None,
                        sandbox=policy.sandbox if policy else None,
                        workdir=workdir,
                    ),
                    error=str(exc),
                    stdout="",
                    stderr="",
                    returncode=None,
                    timed_out=False,
                    rate_limited=False,
                )
            )
            raise

        if outcome.error_text or outcome.returncode not in (None, 0):
            error_text = outcome.error_text or f"{provider} exited with code {outcome.returncode}"
            if is_rate_limited(error_text):
                self._account_mgr.mark_rate_limited(provider, profile.name)
            await self.on_event(
                build_run_failed_event(
                    RunLifecycleContext(
                        session_id=session_id,
                        run_id=run_id,
                        provider=provider,
                        role=role,
                        policy_role=policy.role if policy else None,
                        sandbox=policy.sandbox if policy else None,
                        workdir=workdir,
                    ),
                    error=error_text,
                    stdout=outcome.output,
                    stderr=outcome.stderr,
                    returncode=outcome.returncode,
                    timed_out=outcome.timed_out,
                    rate_limited=outcome.rate_limited or is_rate_limited(error_text),
                )
            )
            raise RuntimeError(error_text)

        self._account_mgr.mark_success(provider, profile.name)
        output = outcome.output
        if output:
            await self.on_event(
                {
                    "session_id": session_id,
                    "run_id": run_id,
                    "type": "message_finalized",
                    "provider": provider,
                    "role": role,
                    "content": output,
                    "stdout": outcome.output,
                    "stderr": outcome.stderr,
                }
            )
        await self.on_event(
            build_run_completed_event(
                RunLifecycleContext(
                    session_id=session_id,
                    run_id=run_id,
                    provider=provider,
                    role=role,
                    policy_role=policy.role if policy else None,
                    sandbox=policy.sandbox if policy else None,
                    workdir=workdir,
                ),
                stdout=outcome.output,
                stderr=outcome.stderr,
                returncode=outcome.returncode,
                timed_out=outcome.timed_out,
                rate_limited=outcome.rate_limited,
            )
        )
        return output

    def _available_providers(self) -> list[str]:
        return [provider for provider in ("claude", "codex", "gemini") if self._account_mgr.pools.get(provider)]

    def _ordered_providers(self, providers: list[str], limit: int | None = None) -> list[str]:
        ordered: list[str] = []
        for provider in providers:
            normalized = provider.strip()
            if not normalized or normalized in ordered:
                continue
            if normalized in {"claude", "codex", "gemini"}:
                ordered.append(normalized)
        if not ordered:
            ordered = self._available_providers()
        if limit is not None:
            ordered = ordered[:limit]
        return ordered

    def default_brainstorm_providers(self, primary_provider: str) -> tuple[list[str], str]:
        candidates = [primary_provider, *self._available_providers()]
        ideators = self._ordered_providers(candidates, limit=3)
        moderator = primary_provider if primary_provider in {"claude", "codex", "gemini"} else (ideators[0] if ideators else "claude")
        if moderator not in ideators and moderator in self._available_providers():
            ideators = [moderator, *ideators]
            ideators = self._ordered_providers(ideators, limit=3)
        return ideators, moderator

    def default_delegate_providers(self, primary_provider: str) -> list[str]:
        candidates = [primary_provider, *self._available_providers()]
        return self._ordered_providers(candidates, limit=3)

    @staticmethod
    def _is_git_repo(path: Path) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    @staticmethod
    def _build_writer_prompt(task: str, findings: list[dict[str, Any]] | None) -> str:
        if not findings:
            return (
                "You are the writer in a writer/critic loop.\n\n"
                f"Task:\n{task}\n\n"
                "Implement the required changes directly in the repository. "
                "Then summarize the concrete changes you made."
            )

        finding_lines = "\n".join(
            f"- [{finding['severity']}] {finding.get('file', '')}: {finding.get('title', '')}".strip()
            for finding in findings
        )
        return (
            "You are continuing a writer/critic loop.\n\n"
            f"Original task:\n{task}\n\n"
            "Address every open critic finding below, then summarize the fixes.\n"
            f"{finding_lines}"
        )

    @staticmethod
    def _build_critic_prompt(
        *,
        task: str,
        writer_output: str,
        repo_state: dict[str, str],
    ) -> str:
        return (
            "You are the critic in a writer/critic loop. Review the actual repository changes.\n\n"
            f"Original task:\n{task}\n\n"
            f"Git status:\n{repo_state.get('status', '(clean)')}\n\n"
            f"Diff stat:\n{repo_state.get('diff_stat', '(no diff stat)')}\n\n"
            f"Full diff:\n{repo_state.get('diff_patch', '(no diff)')[:14000]}\n\n"
            f"Writer summary:\n{writer_output[:4000] or '(no summary provided)'}\n\n"
            "Respond as JSON with this shape:\n"
            '{"status":"needs_work|lgtm","lgtm":true|false,"issues":[{"id":"issue-id","severity":"critical|high|medium|low","kind":"correctness|security|performance|style|other","file":"path/to/file","line":123,"summary":"short issue summary","suggested_fix":"specific fix"}]}\n'
            "If there are no issues, set lgtm to true and issues to []."
        )

    @staticmethod
    def _build_brainstorm_prompt(task: str, ideas: list[BrainstormIdea], pass_index: int) -> str:
        prior = "\n\n".join(
            f"Idea from {idea.provider}:\n{idea.content[:2000]}"
            for idea in ideas
        )
        sections = [
            "You are one participant in a product and engineering brainstorm.",
            f"Task:\n{task}",
            "Provide one distinct implementation strategy with tradeoffs, risks, and first steps.",
        ]
        if prior:
            sections.append("Avoid repeating these existing ideas verbatim:\n" + prior)
        sections.append(f"Label this as idea pass {pass_index}.")
        return "\n\n".join(sections)

    @staticmethod
    def _build_moderator_prompt(task: str, ideas: list[BrainstormIdea]) -> str:
        compiled = "\n\n".join(
            f"{idea.provider}:\n{idea.content[:3000]}"
            for idea in ideas
        )
        return (
            "You are moderating a brainstorm. Synthesize the strongest plan from the ideas below.\n\n"
            f"Task:\n{task}\n\n"
            f"Ideas:\n{compiled}\n\n"
            "Return a concrete recommendation, key tradeoffs, and a short execution plan."
        )

    @staticmethod
    def _build_delegate_prompt(task: str, lane_index: int, provider: str) -> str:
        return (
            "You are one execution lane in a parallel delegate run.\n\n"
            f"Task:\n{task}\n\n"
            f"Lane {lane_index} ({provider}) should pursue an independent solution path or subsystem slice. "
            "Do the work directly in the repository and then summarize the changes, risks, and follow-up."
        )

    @classmethod
    def _report_to_findings(cls, report: Any) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for issue in getattr(report, "issues", []) or []:
            if isinstance(issue, dict):
                issue_get = issue.get
            else:
                issue_get = lambda key, default=None: getattr(issue, key, default)
            raw_severity = issue_get("severity")
            severity_text = getattr(raw_severity, "value", raw_severity) or "medium"
            priority = cls._severity_to_priority(str(severity_text))
            line = issue_get("line")
            findings.append(
                {
                    "severity": priority,
                    "file": issue_get("file", "") or "",
                    "line": line,
                    "line_range": str(line) if line else None,
                    "title": issue_get("summary", "") or "Critic finding",
                    "explanation": issue_get("suggested_fix", "") or issue_get("summary", "") or "Review required.",
                }
            )

        if findings:
            return findings

        return cls._parse_legacy_findings(getattr(report, "raw_text", "") or "")

    @staticmethod
    def _parse_critic_output(raw: str) -> Any:
        try:
            from triad.core.modes.critic import CriticMode

            return CriticMode.parse_critic_output(raw)
        except ModuleNotFoundError:
            parsed = None
            stripped = raw.strip()
            if stripped.startswith("{"):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None

            class FallbackReport:
                def __init__(self, raw_text: str, payload: dict[str, Any] | None) -> None:
                    lower = raw_text.lower()
                    self.issues = (payload or {}).get("issues", [])
                    payload_lgtm = (payload or {}).get("lgtm")
                    self.lgtm = bool(payload_lgtm) if payload_lgtm is not None else any(
                        token in lower for token in ("lgtm", "looks good", "approved", "no issues")
                    )
                    self.raw_text = raw_text

            return FallbackReport(raw, parsed if isinstance(parsed, dict) else None)

    @staticmethod
    def _severity_to_priority(value: str) -> str:
        normalized = value.strip().lower()
        if normalized == "critical":
            return "P0"
        if normalized == "high":
            return "P1"
        if normalized == "low":
            return "P3"
        return "P2"

    @classmethod
    def _parse_legacy_findings(cls, text: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            upper = line.upper()
            priority = next((candidate for candidate in ("P0", "P1", "P2", "P3") if candidate in upper), None)
            if priority is None:
                continue
            findings.append(
                {
                    "severity": priority,
                    "file": "",
                    "line": None,
                    "line_range": None,
                    "title": line[:160],
                    "explanation": line,
                }
            )
        return findings
