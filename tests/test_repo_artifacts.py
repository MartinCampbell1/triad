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


def test_capture_clean_repo(tmp_path: Path):
    repo = tmp_path / "clean"
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
