"""Session browser TUI screen."""
from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from triad.core.storage.ledger import Ledger


class SessionsScreen(Screen):
    BINDINGS = [("escape", "back", "Back")]

    CSS = """
    DataTable { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("[bold]Session History[/bold]")
        yield DataTable(id="sessions-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#sessions-table", DataTable)
        table.add_columns("ID", "Mode", "Status", "Task", "Created")
        self.run_worker(self._load_sessions())

    async def _load_sessions(self) -> None:
        table = self.query_one("#sessions-table", DataTable)
        db_path = Path.home() / ".triad" / "triad.db"
        if not db_path.exists():
            table.add_row("—", "—", "No sessions yet", "—", "—")
            return

        ledger = Ledger(db_path=db_path)
        await ledger.initialize()
        sessions = await ledger.list_sessions(limit=50)
        await ledger.close()

        if not sessions:
            table.add_row("—", "—", "No sessions yet", "—", "—")
            return

        import time
        for s in sessions:
            created = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["created_at"]))
            table.add_row(
                s["id"],
                s["mode"],
                s["status"],
                s["task"][:60],
                created,
            )

    def action_back(self) -> None:
        self.app.pop_screen()
