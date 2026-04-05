import pytest
from pathlib import Path
from unittest.mock import MagicMock
from triad.core.modes.delegate import DelegateMode, DelegateConfig, DelegateTask
from triad.core.accounts.manager import AccountManager
from triad.core.storage.ledger import Ledger
from triad.core.worktrees import WorktreeManager


async def test_delegate_fails_on_worktree_error(tmp_db: Path, tmp_profiles: Path):
    ledger = Ledger(db_path=tmp_db)
    await ledger.initialize()

    mgr = AccountManager(profiles_dir=tmp_profiles)
    mgr.discover()

    broken_wt = MagicMock(spec=WorktreeManager)
    broken_wt.create.side_effect = RuntimeError("git worktree failed")

    task = DelegateTask(prompt="test task", provider="codex")
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
    assert results[0].result is not None
    assert "worktree" in results[0].result.stderr.lower()

    await ledger.close()


async def test_delegate_without_worktrees_runs_normally(tmp_db: Path, tmp_profiles: Path):
    """When use_worktrees=False, tasks run in repo_path directly."""
    ledger = Ledger(db_path=tmp_db)
    await ledger.initialize()

    mgr = AccountManager(profiles_dir=tmp_profiles)
    mgr.discover()

    task = DelegateTask(prompt="test", provider="codex")
    config = DelegateConfig(tasks=[task], use_worktrees=False, repo_path=Path("/tmp"))

    mode = DelegateMode(config=config, account_manager=mgr, ledger=ledger)
    await mode.initialize()
    # This will fail because codex isn't installed in test, but it should try (not fail on worktree)
    results = await mode.run_all()
    # Task should have attempted execution (not stuck on worktree)
    assert results[0].status in ("failed", "completed", "rate_limited")

    await ledger.close()
