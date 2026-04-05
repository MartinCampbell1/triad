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
