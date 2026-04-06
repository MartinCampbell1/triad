from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _run(
    repo_path: Path,
    *args: str,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(repo_path),
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def apply_review_patch(project_path: str, patch: str) -> dict[str, Any]:
    repo_path = Path(project_path).expanduser().resolve()
    if not repo_path.is_dir():
        raise ValueError(f"Project path does not exist: {project_path}")
    if not patch.strip():
        raise ValueError("patch is required")
    patch_input = patch if patch.endswith("\n") else f"{patch}\n"

    repo_root_result = _run(repo_path, "git", "rev-parse", "--show-toplevel")
    if repo_root_result.returncode != 0:
        message = (
            repo_root_result.stderr.strip()
            or repo_root_result.stdout.strip()
            or "Review patch requires a git repository."
        )
        raise ValueError(message)

    repo_root = Path((repo_root_result.stdout or "").strip() or repo_path).resolve()
    check = _run(
        repo_root,
        "git",
        "apply",
        "--check",
        "--recount",
        "--whitespace=nowarn",
        "-",
        input_text=patch_input,
    )
    if check.returncode != 0:
        message = check.stderr.strip() or check.stdout.strip() or "Patch does not apply cleanly."
        raise ValueError(message)

    apply = _run(
        repo_root,
        "git",
        "apply",
        "--recount",
        "--whitespace=nowarn",
        "-",
        input_text=patch_input,
    )
    if apply.returncode != 0:
        message = apply.stderr.strip() or apply.stdout.strip() or "Failed to apply review patch."
        raise ValueError(message)

    diff_stat = _run(repo_root, "git", "diff", "--stat", "--find-renames").stdout.strip()
    status = _run(repo_root, "git", "status", "--short").stdout.strip()
    return {
        "status": "ok",
        "project_path": str(repo_root),
        "diff_stat": diff_stat,
        "status_text": status,
    }
