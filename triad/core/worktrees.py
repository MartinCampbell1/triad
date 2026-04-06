"""Git worktree manager for parallel agent isolation."""
from __future__ import annotations

import re
import shutil
import subprocess
import uuid
from pathlib import Path


class WorktreeManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create(self, repo_path: Path, name: str) -> Path:
        slug = self._slugify_name(name)
        branch = f"triad/{slug}-{uuid.uuid4().hex[:6]}"
        wt_path = self.base_dir / f"{slug}-{uuid.uuid4().hex[:8]}"
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(wt_path)],
            cwd=str(repo_path),
            capture_output=True,
            check=True,
        )
        return wt_path

    def remove(self, wt_path: Path) -> None:
        subprocess.run(
            ["git", "worktree", "remove", str(wt_path), "--force"],
            capture_output=True,
        )
        if wt_path.exists():
            shutil.rmtree(wt_path)

    def list_active(self) -> list[Path]:
        if not self.base_dir.exists():
            return []
        return [p for p in self.base_dir.iterdir() if p.is_dir()]

    def cleanup_all(self) -> int:
        """Remove all worktrees. Returns count removed."""
        removed = 0
        for wt in self.list_active():
            try:
                self.remove(wt)
                removed += 1
            except Exception:
                pass
        return removed

    @staticmethod
    def _slugify_name(name: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip())
        slug = slug.strip("-")
        return slug or "worktree"
