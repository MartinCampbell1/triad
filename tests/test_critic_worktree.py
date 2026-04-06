from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from triad.core.modes.critic import CriticMode, CriticConfig
from triad.core.context.blackboard import Blackboard
from triad.core.models import Profile
from triad.core.providers.base import ExecutionResult


def test_critic_config_has_use_worktree():
    cfg = CriticConfig(writer_provider="claude", critic_provider="codex")
    assert cfg.use_worktree is True


def test_critic_mode_accepts_worktree_manager():
    mode = CriticMode(
        config=CriticConfig(writer_provider="claude", critic_provider="codex"),
        writer_adapter=MagicMock(),
        critic_adapter=MagicMock(),
        writer_profile=Profile(name="a", provider="claude", path="/tmp"),
        critic_profile=Profile(name="b", provider="codex", path="/tmp"),
        ledger=MagicMock(),
        blackboard=Blackboard(task="test"),
        worktree_manager=MagicMock(),
    )
    assert mode.worktree_manager is not None


def test_critic_mode_works_without_worktree_manager():
    mode = CriticMode(
        config=CriticConfig(writer_provider="claude", critic_provider="codex"),
        writer_adapter=MagicMock(),
        critic_adapter=MagicMock(),
        writer_profile=Profile(name="a", provider="claude", path="/tmp"),
        critic_profile=Profile(name="b", provider="codex", path="/tmp"),
        ledger=MagicMock(),
        blackboard=Blackboard(task="test"),
    )
    assert mode.worktree_manager is None
    assert mode._session_workdir is None


def test_critic_has_close_method():
    mode = CriticMode(
        config=CriticConfig(writer_provider="claude", critic_provider="codex"),
        writer_adapter=MagicMock(),
        critic_adapter=MagicMock(),
        writer_profile=Profile(name="a", provider="claude", path="/tmp"),
        critic_profile=Profile(name="b", provider="codex", path="/tmp"),
        ledger=MagicMock(),
        blackboard=Blackboard(task="test"),
    )
    assert hasattr(mode, 'close')


def _make_async_ledger():
    ledger = MagicMock()
    ledger.create_session = AsyncMock(return_value="sess_123")
    ledger.update_session_status = AsyncMock()
    ledger.log_event = AsyncMock()
    ledger.store_artifact = AsyncMock(side_effect=["writer_aid", "critic_aid"])
    return ledger


@pytest.mark.asyncio
async def test_critic_initialize_requires_worktree_manager_when_enabled():
    ledger = _make_async_ledger()
    mode = CriticMode(
        config=CriticConfig(writer_provider="claude", critic_provider="codex", use_worktree=True),
        writer_adapter=MagicMock(),
        critic_adapter=MagicMock(),
        writer_profile=Profile(name="a", provider="claude", path="/tmp"),
        critic_profile=Profile(name="b", provider="codex", path="/tmp"),
        ledger=ledger,
        blackboard=Blackboard(task="test"),
        worktree_manager=None,
    )

    with pytest.raises(RuntimeError, match="requires WorktreeManager"):
        await mode.initialize()

    ledger.update_session_status.assert_awaited_once_with("sess_123", "failed")


@pytest.mark.asyncio
async def test_critic_initialize_fails_closed_on_worktree_error():
    ledger = _make_async_ledger()
    worktree_manager = MagicMock()
    worktree_manager.create.side_effect = RuntimeError("git worktree failed")
    mode = CriticMode(
        config=CriticConfig(writer_provider="claude", critic_provider="codex", use_worktree=True),
        writer_adapter=MagicMock(),
        critic_adapter=MagicMock(),
        writer_profile=Profile(name="a", provider="claude", path="/tmp"),
        critic_profile=Profile(name="b", provider="codex", path="/tmp"),
        ledger=ledger,
        blackboard=Blackboard(task="test"),
        worktree_manager=worktree_manager,
    )

    with pytest.raises(RuntimeError, match="worktree creation failed"):
        await mode.initialize()

    ledger.update_session_status.assert_awaited_once_with("sess_123", "failed")


@pytest.mark.asyncio
async def test_critic_run_round_passes_execution_policies(monkeypatch):
    ledger = _make_async_ledger()
    worktree_manager = MagicMock()
    worktree_manager.create.return_value = Path("/tmp/critic-wt")

    writer_adapter = MagicMock()
    writer_adapter.execute = AsyncMock(return_value=ExecutionResult(
        success=True, returncode=0, stdout="writer output", stderr="", timed_out=False, rate_limited=False,
    ))
    critic_adapter = MagicMock()
    critic_adapter.execute = AsyncMock(return_value=ExecutionResult(
        success=True,
        returncode=0,
        stdout='{"status":"lgtm","issues":[],"lgtm":true}',
        stderr="",
        timed_out=False,
        rate_limited=False,
    ))

    monkeypatch.setattr(
        "triad.core.repo_artifacts.capture_repo_artifacts",
        lambda workdir: {"status": "M x.py", "diff_stat": "1 file changed", "diff_patch": "diff --git"},
    )

    mode = CriticMode(
        config=CriticConfig(writer_provider="claude", critic_provider="codex", workdir=Path("/tmp/repo"), use_worktree=True),
        writer_adapter=writer_adapter,
        critic_adapter=critic_adapter,
        writer_profile=Profile(name="a", provider="claude", path="/tmp"),
        critic_profile=Profile(name="b", provider="codex", path="/tmp"),
        ledger=ledger,
        blackboard=Blackboard(task="test"),
        worktree_manager=worktree_manager,
    )

    await mode.initialize()
    await mode.run_round()

    assert writer_adapter.execute.await_args.kwargs["policy"].role == "writer"
    assert critic_adapter.execute.await_args.kwargs["policy"].role == "critic"


@pytest.mark.asyncio
async def test_critic_close_removes_session_worktree():
    ledger = _make_async_ledger()
    worktree_manager = MagicMock()
    wt_path = Path("/tmp/critic-wt")
    worktree_manager.create.return_value = wt_path

    mode = CriticMode(
        config=CriticConfig(writer_provider="claude", critic_provider="codex", workdir=Path("/tmp/repo"), use_worktree=True),
        writer_adapter=MagicMock(),
        critic_adapter=MagicMock(),
        writer_profile=Profile(name="a", provider="claude", path="/tmp"),
        critic_profile=Profile(name="b", provider="codex", path="/tmp"),
        ledger=ledger,
        blackboard=Blackboard(task="test"),
        worktree_manager=worktree_manager,
    )

    await mode.initialize()
    await mode.close()

    worktree_manager.remove.assert_called_once_with(wt_path)
