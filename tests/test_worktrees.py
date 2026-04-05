import subprocess
from pathlib import Path
import pytest
from triad.core.worktrees import WorktreeManager


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)
    (repo / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
    return repo


def test_create_worktree(git_repo: Path, tmp_path: Path):
    mgr = WorktreeManager(base_dir=tmp_path / "worktrees")
    wt_path = mgr.create(repo_path=git_repo, name="task-1")
    assert wt_path.exists()
    assert (wt_path / "README.md").exists()


def test_create_multiple_worktrees(git_repo: Path, tmp_path: Path):
    mgr = WorktreeManager(base_dir=tmp_path / "worktrees")
    wt1 = mgr.create(repo_path=git_repo, name="task-1")
    wt2 = mgr.create(repo_path=git_repo, name="task-2")
    assert wt1 != wt2
    assert wt1.exists()
    assert wt2.exists()


def test_remove_worktree(git_repo: Path, tmp_path: Path):
    mgr = WorktreeManager(base_dir=tmp_path / "worktrees")
    wt_path = mgr.create(repo_path=git_repo, name="task-1")
    mgr.remove(wt_path)
    assert not wt_path.exists()


def test_list_worktrees(git_repo: Path, tmp_path: Path):
    mgr = WorktreeManager(base_dir=tmp_path / "worktrees")
    mgr.create(repo_path=git_repo, name="task-1")
    mgr.create(repo_path=git_repo, name="task-2")
    worktrees = mgr.list_active()
    assert len(worktrees) >= 2
