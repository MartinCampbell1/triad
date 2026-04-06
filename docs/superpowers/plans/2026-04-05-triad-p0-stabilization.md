# Triad P0 Stabilization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 7 critical P0 bugs identified by the GPT-5.4 Pro audit that make Triad unsafe or broken for daily use.

**Architecture:** Targeted fixes to existing modules — no new subsystems. Each fix is independent and committed separately. After all 7, the system is safe for real use.

**Tech Stack:** Python 3.12+, asyncio, Textual, aiosqlite

**Audit source:** `/Users/martin/Downloads/triad-ispravleniya-versii-2.0.md`

---

## Summary of P0 Issues

| # | Issue | File(s) | Risk |
|---|-------|---------|------|
| P0-1 | `action_solo()` uses `run_until_complete` inside running event loop | `tui/screens/main.py` | Crash on solo launch |
| P0-2 | `/swap` changes UI label but not real orchestration | `tui/screens/critic.py` | Silent semantic corruption |
| P0-3 | Critic has no read-only policy — can write code | `providers/*.py`, `modes/critic.py` | Breaks trust boundary |
| P0-4 | Critic reviews stdout, not actual git diff | `modes/critic.py` | Reviews wrong thing |
| P0-5 | Critic mode works in live cwd, not session worktree | `modes/critic.py` | Corrupts user's repo |
| P0-6 | Delegate silently falls back to live repo on worktree failure | `modes/delegate.py` | Dangerous surprise |
| P0-7 | Dangerous auth env vars allowed by default | `core/env.py`, `core/policy.py` | Wrong billing mode |

---

## Task 1: Fix solo launch event loop crash (P0-1)

**Files:**
- Modify: `triad/tui/screens/main.py:49-78`
- Test: `tests/test_solo_mode.py` (existing, verify still passes)

- [ ] **Step 1: Write failing test for async solo**

```python
# tests/test_solo_launch.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path


async def test_solo_action_does_not_use_run_until_complete():
    """Verify that action_solo doesn't call loop.run_until_complete."""
    # Read main.py source and assert no run_until_complete
    source = Path("/Users/martin/triad/triad/tui/screens/main.py").read_text()
    assert "run_until_complete" not in source, (
        "action_solo must not use run_until_complete inside Textual's running event loop"
    )


async def test_solo_action_uses_asyncio_to_thread():
    """Verify that action_solo uses asyncio.to_thread for blocking launch."""
    source = Path("/Users/martin/triad/triad/tui/screens/main.py").read_text()
    assert "to_thread" in source or "run_worker" in source, (
        "action_solo must use asyncio.to_thread or run_worker for blocking operations"
    )
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_solo_launch.py -v`
Expected: FAIL — `run_until_complete` IS in the source

- [ ] **Step 3: Rewrite action_solo as async**

Replace `triad/tui/screens/main.py` lines 49-78 with:

```python
    async def action_solo(self) -> None:
        import asyncio
        from pathlib import Path

        from triad.core.accounts.manager import AccountManager
        from triad.core.modes.solo import SoloMode
        from triad.core.storage.ledger import Ledger

        config_obj = self.app.triad_config  # type: ignore[attr-defined]

        db_path = config_obj.db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        ledger = Ledger(db_path=db_path)
        await ledger.initialize()

        mgr = AccountManager(profiles_dir=config_obj.profiles_dir)
        mgr.discover()

        solo = SoloMode(ledger=ledger, account_manager=mgr)
        await solo.pre_launch()

        exit_code = 1
        try:
            with self.app.suspend():
                exit_code = await asyncio.to_thread(solo.launch, Path.cwd())
        finally:
            await solo.post_launch(exit_code)
            await ledger.close()

        self.notify(f"Claude Code exited (code {exit_code}). Session logged.")
```

- [ ] **Step 4: Run test — verify it passes**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_solo_launch.py tests/test_solo_mode.py -v`
Expected: All pass

- [ ] **Step 5: Run full suite**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/ -v --tb=short`
Expected: All 79+ tests pass

- [ ] **Step 6: Commit**

```bash
cd /Users/martin/triad
git add triad/tui/screens/main.py tests/test_solo_launch.py
git commit -m "fix(P0-1): rewrite action_solo as async — no run_until_complete inside Textual loop"
```

---

## Task 2: Fix /swap to actually change orchestration (P0-2)

**Files:**
- Modify: `triad/tui/screens/critic.py:308-322`
- Test: `tests/test_swap.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_swap.py
from unittest.mock import MagicMock
from triad.core.modes.critic import CriticMode, CriticConfig
from triad.core.context.blackboard import Blackboard
from triad.core.models import Profile


def test_swap_changes_real_mode_state():
    """After swap, the CriticMode's adapters and config must reflect new roles."""
    writer_adapter = MagicMock()
    writer_adapter.provider = "claude"
    critic_adapter = MagicMock()
    critic_adapter.provider = "codex"

    writer_profile = Profile(name="acc1", provider="claude", path="/tmp/c")
    critic_profile = Profile(name="acc1", provider="codex", path="/tmp/x")

    config = CriticConfig(writer_provider="claude", critic_provider="codex")
    mode = CriticMode(
        config=config,
        writer_adapter=writer_adapter,
        critic_adapter=critic_adapter,
        writer_profile=writer_profile,
        critic_profile=critic_profile,
        ledger=MagicMock(),
        blackboard=Blackboard(task="test"),
    )

    # Perform swap
    mode.swap_roles()

    assert mode.config.writer_provider == "codex"
    assert mode.config.critic_provider == "claude"
    assert mode.writer_adapter is critic_adapter
    assert mode.critic_adapter is writer_adapter
    assert mode.writer_profile is critic_profile
    assert mode.critic_profile is writer_profile
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_swap.py -v`
Expected: FAIL — `AttributeError: 'CriticMode' object has no attribute 'swap_roles'`

- [ ] **Step 3: Add swap_roles method to CriticMode**

Add to `triad/core/modes/critic.py` class CriticMode, after `rounds` property:

```python
    def swap_roles(self) -> None:
        """Swap writer and critic roles — adapters, profiles, and config."""
        self.writer_adapter, self.critic_adapter = self.critic_adapter, self.writer_adapter
        self.writer_profile, self.critic_profile = self.critic_profile, self.writer_profile
        self.config.writer_provider, self.config.critic_provider = (
            self.config.critic_provider,
            self.config.writer_provider,
        )
```

- [ ] **Step 4: Update CriticScreen.action_swap to use swap_roles**

Replace `triad/tui/screens/critic.py` lines 308-322 with:

```python
    def action_swap(self) -> None:
        if not self._critic_mode or self._running:
            return

        mode = self._critic_mode
        mode.swap_roles()

        self.writer_provider = mode.config.writer_provider
        self.critic_provider = mode.config.critic_provider

        log = self.query_one("#log-area", RichLog)
        log.write(
            f"\n[bold magenta]Roles swapped![/bold magenta] "
            f"Writer: [cyan]{self.writer_provider}[/cyan] | "
            f"Critic: [yellow]{self.critic_provider}[/yellow]"
        )
        self.query_one("#status-bar", Static).update(
            f"[bold]Critic Mode[/bold] — Writer: [cyan]{self.writer_provider}[/cyan] | "
            f"Critic: [yellow]{self.critic_provider}[/yellow]"
        )
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_swap.py tests/test_critic_mode.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
cd /Users/martin/triad
git add triad/core/modes/critic.py triad/tui/screens/critic.py tests/test_swap.py
git commit -m "fix(P0-2): swap_roles changes real adapters/profiles/config, not just UI labels"
```

---

## Task 3: Add ExecutionPolicy — critic is read-only (P0-3)

**Files:**
- Create: `triad/core/execution_policy.py`
- Modify: `triad/core/providers/base.py`
- Modify: `triad/core/providers/claude.py`
- Modify: `triad/core/providers/codex.py`
- Test: `tests/test_execution_policy.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_execution_policy.py
from triad.core.execution_policy import ExecutionPolicy
from triad.core.providers.claude import ClaudeAdapter
from triad.core.providers.codex import CodexAdapter


def test_writer_policy():
    policy = ExecutionPolicy.writer()
    assert policy.role == "writer"
    assert policy.sandbox == "workspace_write"


def test_critic_policy():
    policy = ExecutionPolicy.critic()
    assert policy.role == "critic"
    assert policy.sandbox == "read_only"


def test_claude_headless_writer_command():
    adapter = ClaudeAdapter()
    policy = ExecutionPolicy.writer()
    cmd = adapter.headless_command("Fix bug", policy=policy)
    assert "--permission-mode" not in cmd or "acceptEdits" in " ".join(cmd)


def test_claude_headless_critic_command():
    adapter = ClaudeAdapter()
    policy = ExecutionPolicy.critic()
    cmd = adapter.headless_command("Review code", policy=policy)
    joined = " ".join(cmd)
    assert "--allowedTools" in joined or "--permission-mode" in joined


def test_codex_headless_writer_command():
    adapter = CodexAdapter()
    policy = ExecutionPolicy.writer()
    cmd = adapter.headless_command("Fix bug", policy=policy)
    assert "--full-auto" in cmd


def test_codex_headless_critic_command():
    adapter = CodexAdapter()
    policy = ExecutionPolicy.critic()
    cmd = adapter.headless_command("Review code", policy=policy)
    joined = " ".join(cmd)
    assert "read-only" in joined or "review" in joined
```

- [ ] **Step 2: Run test — verify fails**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_execution_policy.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ExecutionPolicy**

```python
# triad/core/execution_policy.py
"""Role-aware execution policy for provider commands."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ExecutionPolicy:
    role: Literal["writer", "critic", "delegate", "solo"]
    sandbox: Literal["read_only", "workspace_write", "full_access"]

    @classmethod
    def writer(cls) -> ExecutionPolicy:
        return cls(role="writer", sandbox="workspace_write")

    @classmethod
    def critic(cls) -> ExecutionPolicy:
        return cls(role="critic", sandbox="read_only")

    @classmethod
    def delegate(cls) -> ExecutionPolicy:
        return cls(role="delegate", sandbox="workspace_write")

    @classmethod
    def solo(cls) -> ExecutionPolicy:
        return cls(role="solo", sandbox="full_access")
```

- [ ] **Step 4: Update ClaudeAdapter to accept policy**

Replace `triad/core/providers/claude.py` `headless_command`:

```python
    def headless_command(self, prompt: str, session_id: str | None = None, policy: "ExecutionPolicy | None" = None, **kwargs) -> list[str]:
        from triad.core.execution_policy import ExecutionPolicy
        cmd = ["claude", "-p", prompt, "--output-format", "stream-json"]
        if session_id:
            cmd.extend(["--resume", session_id])
        if policy and policy.sandbox == "read_only":
            cmd.extend(["--permission-mode", "bypassPermissions", "--allowedTools", "Read,Grep,Glob,Bash(git diff *),Bash(git status *),Bash(git log *)"])
        return cmd
```

- [ ] **Step 5: Update CodexAdapter to accept policy**

Replace `triad/core/providers/codex.py` `headless_command`:

```python
    def headless_command(self, prompt: str, model: str | None = None, policy: "ExecutionPolicy | None" = None, **kwargs) -> list[str]:
        from triad.core.execution_policy import ExecutionPolicy
        if policy and policy.sandbox == "read_only":
            cmd = ["codex", "exec", "--sandbox", "read-only"]
        else:
            cmd = ["codex", "exec", "--full-auto"]
        if model:
            cmd.extend(["-m", model])
        cmd.append(prompt)
        return cmd
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_execution_policy.py tests/test_providers.py -v`
Expected: All pass (including old provider tests — policy is optional param)

- [ ] **Step 7: Commit**

```bash
cd /Users/martin/triad
git add triad/core/execution_policy.py triad/core/providers/claude.py triad/core/providers/codex.py tests/test_execution_policy.py
git commit -m "fix(P0-3): add ExecutionPolicy — critic is read-only, writer can write"
```

---

## Task 4: Critic reviews git diff, not stdout (P0-4)

**Files:**
- Create: `triad/core/repo_artifacts.py`
- Modify: `triad/core/modes/critic.py`
- Test: `tests/test_repo_artifacts.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_repo_artifacts.py
import subprocess
from pathlib import Path
import pytest
from triad.core.repo_artifacts import capture_repo_artifacts


@pytest.fixture
def git_repo_with_changes(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, capture_output=True)
    (repo / "main.py").write_text("print('hello')\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
    # Make a change
    (repo / "main.py").write_text("print('hello world')\n")
    return repo


def test_capture_has_status(git_repo_with_changes: Path):
    artifacts = capture_repo_artifacts(git_repo_with_changes)
    assert "status" in artifacts
    assert "main.py" in artifacts["status"]


def test_capture_has_diff(git_repo_with_changes: Path):
    artifacts = capture_repo_artifacts(git_repo_with_changes)
    assert "diff_patch" in artifacts
    assert "hello world" in artifacts["diff_patch"]


def test_capture_has_stat(git_repo_with_changes: Path):
    artifacts = capture_repo_artifacts(git_repo_with_changes)
    assert "diff_stat" in artifacts
    assert "main.py" in artifacts["diff_stat"]


def test_capture_empty_repo(tmp_path: Path):
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, capture_output=True)
    (repo / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
    artifacts = capture_repo_artifacts(repo)
    assert artifacts["status"] == ""
    assert artifacts["diff_patch"] == ""
```

- [ ] **Step 2: Run test — verify fails**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_repo_artifacts.py -v`
Expected: FAIL

- [ ] **Step 3: Implement repo_artifacts**

```python
# triad/core/repo_artifacts.py
"""Capture git repository state as artifacts for critic review."""
from __future__ import annotations

import subprocess
from pathlib import Path


def capture_repo_artifacts(workdir: Path) -> dict[str, str]:
    """Capture current repo state: status, diff stat, and full diff patch."""
    def run(*args: str) -> str:
        result = subprocess.run(
            list(args),
            cwd=str(workdir),
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip()

    return {
        "status": run("git", "status", "--short"),
        "diff_stat": run("git", "diff", "--stat"),
        "diff_patch": run("git", "diff", "--patch", "--find-renames"),
    }
```

- [ ] **Step 4: Update critic prompt to use git diff**

In `triad/core/modes/critic.py`, replace `_CRITIC_PROMPT`:

```python
_CRITIC_PROMPT = """You are a thorough code reviewer. Be specific and actionable.

## Original Task
{task}

## Git Status
{git_status}

## Changes (git diff --stat)
{diff_stat}

## Full Diff
{diff_patch}

## Writer Summary
{writer_summary}

Review the actual code changes shown in the diff above. Output your review as JSON:
{{"status": "needs_work" or "lgtm", "issues": [{{"id": "...", "severity": "critical|high|medium|low", "kind": "security|correctness|performance|style", "file": "...", "summary": "...", "suggested_fix": "..."}}], "lgtm": true or false}}

If no issues, set lgtm to true and issues to []."""
```

- [ ] **Step 5: Update run_round to capture repo artifacts**

In `triad/core/modes/critic.py`, in `run_round()`, after writer executes and before critic prompt, add:

```python
        # Capture actual repo changes instead of relying on stdout
        from triad.core.repo_artifacts import capture_repo_artifacts
        repo_state = capture_repo_artifacts(self.config.workdir)

        critic_prompt = _CRITIC_PROMPT.format(
            task=self.blackboard.task,
            git_status=repo_state["status"],
            diff_stat=repo_state["diff_stat"],
            diff_patch=repo_state["diff_patch"][:12000],
            writer_summary=writer_output[:2000],
        )
```

Replace the old critic_prompt formatting (lines 128-131) with this.

- [ ] **Step 6: Run tests**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_repo_artifacts.py tests/test_critic_mode.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
cd /Users/martin/triad
git add triad/core/repo_artifacts.py triad/core/modes/critic.py tests/test_repo_artifacts.py
git commit -m "fix(P0-4): critic reviews git diff and repo state, not stdout"
```

---

## Task 5: Critic mode uses session-scoped worktree (P0-5)

**Files:**
- Modify: `triad/core/modes/critic.py`
- Modify: `triad/tui/screens/critic.py`
- Test: `tests/test_critic_worktree.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_critic_worktree.py
import subprocess
from pathlib import Path
import pytest
from triad.core.worktrees import WorktreeManager


def test_critic_config_accepts_worktree_manager():
    from triad.core.modes.critic import CriticConfig
    cfg = CriticConfig(writer_provider="claude", critic_provider="codex")
    assert hasattr(cfg, 'use_worktree')


def test_critic_mode_has_worktree_manager():
    from triad.core.modes.critic import CriticMode
    from triad.core.context.blackboard import Blackboard
    from triad.core.models import Profile
    from unittest.mock import MagicMock

    mode = CriticMode(
        config=MagicMock(),
        writer_adapter=MagicMock(),
        critic_adapter=MagicMock(),
        writer_profile=Profile(name="a", provider="claude", path="/tmp"),
        critic_profile=Profile(name="b", provider="codex", path="/tmp"),
        ledger=MagicMock(),
        blackboard=Blackboard(task="test"),
        worktree_manager=None,
    )
    assert hasattr(mode, 'worktree_manager')
```

- [ ] **Step 2: Run test — verify fails**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_critic_worktree.py -v`
Expected: FAIL

- [ ] **Step 3: Add worktree support to CriticConfig and CriticMode**

In `triad/core/modes/critic.py`:

Update `CriticConfig`:
```python
@dataclass
class CriticConfig:
    writer_provider: str
    critic_provider: str
    max_rounds: int = 5
    workdir: Path = field(default_factory=lambda: Path.cwd())
    use_worktree: bool = True
```

Update `CriticMode.__init__` to accept `worktree_manager`:
```python
    def __init__(
        self,
        config: CriticConfig,
        writer_adapter: ProviderAdapter,
        critic_adapter: ProviderAdapter,
        writer_profile: Profile,
        critic_profile: Profile,
        ledger: Ledger,
        blackboard: Blackboard,
        worktree_manager: "WorktreeManager | None" = None,
    ):
        # ... existing fields ...
        self.worktree_manager = worktree_manager
        self._session_workdir: Path | None = None
```

Update `initialize()` to create worktree:
```python
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

        # Create session-scoped worktree
        if self.config.use_worktree and self.worktree_manager:
            from triad.core.worktrees import WorktreeManager
            try:
                self._session_workdir = self.worktree_manager.create(
                    repo_path=self.config.workdir,
                    name=f"critic-{self.session_id}",
                )
            except Exception:
                self._session_workdir = None
        if self._session_workdir is None:
            self._session_workdir = self.config.workdir

        return self.session_id
```

In `run_round()`, replace all `self.config.workdir` with `self._session_workdir`.

Add `close()` method:
```python
    async def close(self) -> None:
        """Clean up resources — close ledger, optionally remove worktree."""
        if self.session_id:
            await self.ledger.log_event(self.session_id, "session.closed")
        await self.ledger.close()
```

- [ ] **Step 4: Update CriticScreen to pass worktree_manager**

In `triad/tui/screens/critic.py`, in `_start_critic()`, add worktree_manager creation:

```python
            from triad.core.worktrees import WorktreeManager
            worktree_mgr = WorktreeManager(base_dir=config_obj.worktrees_dir)

            self._critic_mode = CriticMode(
                config=config,
                writer_adapter=writer_adapter,
                critic_adapter=critic_adapter,
                writer_profile=writer_profile,
                critic_profile=critic_profile,
                ledger=ledger,
                blackboard=blackboard,
                worktree_manager=worktree_mgr,
            )
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_critic_worktree.py tests/test_critic_mode.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
cd /Users/martin/triad
git add triad/core/modes/critic.py triad/tui/screens/critic.py tests/test_critic_worktree.py
git commit -m "fix(P0-5): critic mode uses session-scoped worktree, not live cwd"
```

---

## Task 6: Delegate fails closed on worktree failure (P0-6)

**Files:**
- Modify: `triad/core/modes/delegate.py:89-98`
- Test: `tests/test_delegate_failclose.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_delegate_failclose.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from triad.core.modes.delegate import DelegateMode, DelegateConfig, DelegateTask
from triad.core.accounts.manager import AccountManager
from triad.core.storage.ledger import Ledger
from triad.core.worktrees import WorktreeManager
from triad.core.models import Profile


async def test_delegate_fails_on_worktree_error(tmp_db: Path, tmp_profiles: Path):
    ledger = Ledger(db_path=tmp_db)
    await ledger.initialize()

    mgr = AccountManager(profiles_dir=tmp_profiles)
    mgr.discover()

    # Worktree manager that always fails
    broken_wt = MagicMock(spec=WorktreeManager)
    broken_wt.create.side_effect = RuntimeError("git worktree failed")

    task = DelegateTask(prompt="test", provider="codex")
    config = DelegateConfig(tasks=[task], use_worktrees=True, repo_path=Path("/tmp"))

    mode = DelegateMode(
        config=config,
        account_manager=mgr,
        ledger=ledger,
        worktree_manager=broken_wt,
    )
    await mode.initialize()
    results = await mode.run_all()

    assert results[0].status == "failed"
    assert "worktree" in results[0].result.stderr.lower()

    await ledger.close()
```

- [ ] **Step 2: Run test — verify fails**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_delegate_failclose.py -v`
Expected: FAIL — task status is not "failed" (currently silently continues)

- [ ] **Step 3: Fix delegate to fail-closed**

Replace `triad/core/modes/delegate.py` lines 89-98 with:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_delegate_failclose.py tests/test_delegate_mode.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
cd /Users/martin/triad
git add triad/core/modes/delegate.py tests/test_delegate_failclose.py
git commit -m "fix(P0-6): delegate fails closed on worktree error — never silently uses live repo"
```

---

## Task 7: Dangerous auth env vars are default-deny (P0-7)

**Files:**
- Modify: `triad/core/env.py`
- Modify: `triad/core/policy.py`
- Modify: `tests/test_env.py`
- Modify: `tests/test_policy.py`

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_env.py:

def test_default_strips_anthropic_api_key():
    source = {"PATH": "/usr/bin", "ANTHROPIC_API_KEY": "sk-ant-xxx"}
    result = build_runtime_base_env(source)
    assert "ANTHROPIC_API_KEY" not in result


def test_default_strips_openai_api_key():
    source = {"PATH": "/usr/bin", "OPENAI_API_KEY": "sk-xxx"}
    result = build_runtime_base_env(source)
    assert "OPENAI_API_KEY" not in result


def test_explicit_allow_dangerous():
    source = {"PATH": "/usr/bin", "ANTHROPIC_API_KEY": "sk-ant-xxx"}
    result = build_runtime_base_env(source, allow_dangerous_auth=True)
    assert "ANTHROPIC_API_KEY" in result
```

- [ ] **Step 2: Run tests — verify fails**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/test_env.py -v`
Expected: FAIL — ANTHROPIC_API_KEY currently passes through

- [ ] **Step 3: Update env.py with default-deny for dangerous keys**

Replace `triad/core/env.py`:

```python
"""Runtime environment sanitization for CLI subprocess invocations."""
from __future__ import annotations

import os
from collections.abc import Mapping

RUNTIME_ENV_EXACT_ALLOWLIST: frozenset[str] = frozenset({
    "PATH", "HOME", "SHELL", "TERM", "LANG", "LC_ALL", "LC_CTYPE",
    "LC_COLLATE", "LC_MESSAGES", "TZ", "TMPDIR", "TMP", "TEMP",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE", "NO_COLOR", "COLORTERM", "CI",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "NVM_DIR", "NVM_BIN",
})

RUNTIME_ENV_PREFIX_ALLOWLIST: tuple[str, ...] = (
    "TRIAD_", "CODEX_", "CLAUDE_", "OPENAI_", "ANTHROPIC_",
    "GOOGLE_", "GEMINI_",
)

DANGEROUS_AUTH_KEYS: frozenset[str] = frozenset({
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
})


def runtime_env_key_allowed(key: str) -> bool:
    """Return whether an inherited environment key is safe to forward."""
    normalized = str(key or "").strip()
    if not normalized:
        return False
    if normalized in RUNTIME_ENV_EXACT_ALLOWLIST:
        return True
    return any(normalized.startswith(prefix) for prefix in RUNTIME_ENV_PREFIX_ALLOWLIST)


def build_runtime_base_env(
    base_env: Mapping[str, str] | None = None,
    allow_dangerous_auth: bool = False,
) -> dict[str, str]:
    """Return a sanitized runtime env. Dangerous auth keys stripped by default."""
    source = dict(base_env) if base_env is not None else dict(os.environ)
    sanitized = {
        str(k): str(v)
        for k, v in source.items()
        if runtime_env_key_allowed(str(k))
    }

    if not allow_dangerous_auth:
        for key in DANGEROUS_AUTH_KEYS:
            sanitized.pop(key, None)

    sanitized.setdefault("PATH", str(source.get("PATH") or os.defpath))
    return sanitized
```

- [ ] **Step 4: Update policy.py to make warnings more explicit**

Replace `triad/core/policy.py`:

```python
"""PolicyGuard — safety checks before launching providers."""
from __future__ import annotations

import os
from collections.abc import Mapping
from triad.core.env import DANGEROUS_AUTH_KEYS

_DANGEROUS_KEY_WARNINGS = {
    "ANTHROPIC_API_KEY": "Claude will use API billing instead of subscription. Stripped by default.",
    "OPENAI_API_KEY": "Codex may use API billing. Stripped by default.",
    "GOOGLE_API_KEY": "Gemini may use API billing. Stripped by default.",
    "GEMINI_API_KEY": "Gemini may use API billing. Stripped by default.",
}


class PolicyGuard:
    def check_environment(self, env: Mapping[str, str]) -> list[str]:
        warnings: list[str] = []
        for key, msg in _DANGEROUS_KEY_WARNINGS.items():
            if key in env and env[key]:
                warnings.append(f"WARNING: {key} detected in shell environment. {msg}")
        return warnings
```

- [ ] **Step 5: Run ALL tests**

Run: `cd /Users/martin/triad && .venv/bin/pytest tests/ -v --tb=short`
Expected: All pass (old tests still work because `allow_dangerous_auth` defaults to False)

- [ ] **Step 6: Commit**

```bash
cd /Users/martin/triad
git add triad/core/env.py triad/core/policy.py tests/test_env.py
git commit -m "fix(P0-7): dangerous auth env vars (API keys) are default-deny"
```

---

## Task 8: Final verification — all P0 fixes integrated

- [ ] **Step 1: Run full test suite with coverage**

```bash
cd /Users/martin/triad && .venv/bin/pytest tests/ -v --cov=triad --cov-report=term-missing
```

Expected: All tests pass, no regressions.

- [ ] **Step 2: Verify git log shows all 7 P0 fixes**

```bash
cd /Users/martin/triad && git log --oneline | head -10
```

Expected: 7 new commits with `fix(P0-N)` prefixes.

- [ ] **Step 3: Commit summary**

```bash
cd /Users/martin/triad
git tag v0.2.0-p0-stable
```

---

## Summary

| Task | P0 Issue | Fix |
|------|----------|-----|
| 1 | Solo crashes on running event loop | `async action_solo()` + `asyncio.to_thread` |
| 2 | /swap only changes labels | `swap_roles()` method on CriticMode |
| 3 | Critic can write code | `ExecutionPolicy` with read-only sandbox |
| 4 | Critic reviews stdout not diff | `capture_repo_artifacts()` + new prompt |
| 5 | Critic works in live cwd | Session-scoped worktree |
| 6 | Delegate silently falls back | Fail-closed on worktree error |
| 7 | API keys leak through env | `DANGEROUS_AUTH_KEYS` default-deny |
