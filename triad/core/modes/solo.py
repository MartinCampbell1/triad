"""Solo mode — suspend/handoff to official Claude Code."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from triad.core.accounts.manager import AccountManager
from triad.core.providers import get_adapter
from triad.core.storage.ledger import Ledger


class SoloMode:
    """Manage solo mode: suspend TUI, launch claude, log session."""

    def __init__(self, ledger: Ledger, account_manager: AccountManager):
        self.ledger = ledger
        self.account_manager = account_manager
        self.session_id: str | None = None

    async def pre_launch(self) -> str:
        """Create a session entry before launching claude."""
        self.session_id = await self.ledger.create_session(
            mode="solo",
            task="Interactive Claude Code session",
        )
        await self.ledger.log_event(
            self.session_id, "solo.started",
            agent="claude/interactive",
        )
        return self.session_id

    def launch(self, workdir: Path) -> int:
        """Launch claude interactively (blocking). Call inside app.suspend()."""
        profile = self.account_manager.get_next("claude")
        adapter = get_adapter("claude")

        if profile:
            return adapter.run_interactive(profile, workdir)
        else:
            return subprocess.run(["claude"], cwd=str(workdir)).returncode

    async def post_launch(self, exit_code: int) -> None:
        """Log session completion after returning from claude."""
        if self.session_id:
            status = "completed" if exit_code == 0 else "failed"
            await self.ledger.log_event(
                self.session_id, "solo.finished",
                agent="claude/interactive",
                content=f"exit_code={exit_code}",
            )
            await self.ledger.update_session_status(self.session_id, status)
