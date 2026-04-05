"""Delegate mode — parallel task dispatch to multiple providers."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from triad.core.accounts.manager import AccountManager
from triad.core.models import Profile
from triad.core.modes.base import ModeState
from triad.core.providers import get_adapter
from triad.core.providers.base import ExecutionResult
from triad.core.storage.ledger import Ledger
from triad.core.worktrees import WorktreeManager


@dataclass
class DelegateTask:
    prompt: str
    provider: str
    status: str = "pending"
    result: ExecutionResult | None = None
    worktree_path: Path | None = None
    profile_used: Profile | None = None


@dataclass
class DelegateConfig:
    tasks: list[DelegateTask] = field(default_factory=list)
    timeout: int = 1800
    use_worktrees: bool = True
    repo_path: Path = field(default_factory=lambda: Path.cwd())


class DelegateMode:
    def __init__(
        self,
        config: DelegateConfig,
        account_manager: AccountManager,
        ledger: Ledger,
        worktree_manager: WorktreeManager | None = None,
        on_task_started: Callable[[DelegateTask], None] | None = None,
        on_task_completed: Callable[[DelegateTask], None] | None = None,
    ):
        self.config = config
        self.account_manager = account_manager
        self.ledger = ledger
        self.worktree_manager = worktree_manager
        self.on_task_started = on_task_started
        self.on_task_completed = on_task_completed
        self.state = ModeState.IDLE
        self.session_id: str | None = None

    async def initialize(self) -> str:
        task_summary = "; ".join(f"{t.provider}: {t.prompt[:50]}" for t in self.config.tasks)
        self.session_id = await self.ledger.create_session(
            mode="delegate",
            task=task_summary,
            config_json=json.dumps({"task_count": len(self.config.tasks)}),
        )
        self.state = ModeState.RUNNING
        return self.session_id

    async def run_all(self) -> list[DelegateTask]:
        coros = [self._run_task(task) for task in self.config.tasks]
        await asyncio.gather(*coros, return_exceptions=True)
        self.state = ModeState.COMPLETED
        await self.ledger.update_session_status(self.session_id, "completed")
        return self.config.tasks

    async def _run_task(self, task: DelegateTask) -> None:
        adapter = get_adapter(task.provider)
        profile = self.account_manager.get_next(task.provider)
        if profile is None:
            task.status = "failed"
            task.result = ExecutionResult(
                success=False, returncode=None,
                stdout="", stderr=f"No available {task.provider} profiles",
                timed_out=False, rate_limited=False,
            )
            return

        task.profile_used = profile
        task.status = "running"

        workdir = self.config.repo_path
        if self.config.use_worktrees and self.worktree_manager:
            try:
                wt_path = self.worktree_manager.create(
                    repo_path=self.config.repo_path,
                    name=f"delegate-{task.provider}-{profile.name}",
                )
                task.worktree_path = wt_path
                workdir = wt_path
            except Exception as exc:
                task.status = "failed"
                task.result = ExecutionResult(
                    success=False,
                    returncode=None,
                    stdout="",
                    stderr=f"Worktree creation failed: {exc}",
                    timed_out=False,
                    rate_limited=False,
                )
                await self.ledger.log_event(
                    self.session_id,
                    "lane.failed",
                    agent=f"{task.provider}/{profile.name}",
                    content=task.result.stderr,
                )
                if self.on_task_completed:
                    self.on_task_completed(task)
                return

        if self.on_task_started:
            self.on_task_started(task)

        await self.ledger.log_event(
            self.session_id, "lane.started",
            agent=f"{task.provider}/{profile.name}",
            content=task.prompt[:200],
        )

        result = await adapter.execute(
            profile=profile, prompt=task.prompt,
            workdir=workdir, timeout=self.config.timeout,
        )
        task.result = result

        if result.rate_limited:
            self.account_manager.mark_rate_limited(task.provider, profile.name)
            task.status = "rate_limited"
        elif result.success:
            self.account_manager.mark_success(task.provider, profile.name)
            task.status = "completed"
        else:
            task.status = "failed"

        await self.ledger.log_event(
            self.session_id, f"lane.{task.status}",
            agent=f"{task.provider}/{profile.name}",
            content=result.stdout[:1000] if result.stdout else result.stderr[:1000],
        )

        if self.on_task_completed:
            self.on_task_completed(task)
