"""Account status TUI screen."""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from triad.core.accounts.manager import AccountManager


class AccountsScreen(Screen):
    BINDINGS = [("escape", "back", "Back")]

    CSS = """
    DataTable { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("[bold]Account Status[/bold]")
        yield DataTable(id="accounts-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#accounts-table", DataTable)
        table.add_columns("Provider", "Account", "Status", "Requests", "Errors")

        profiles_dir = Path.home() / ".cli-profiles"
        if not profiles_dir.exists():
            table.add_row("—", "—", "No profiles directory", "—", "—")
            return

        mgr = AccountManager(profiles_dir=profiles_dir)
        mgr.discover()

        if not mgr.pools:
            table.add_row("—", "—", "No profiles found", "—", "—")
            return

        for provider, profiles in mgr.pools.items():
            for p in profiles:
                status = "[green]✓ Available[/green]" if p.check_available() else "[red]✗ Cooldown[/red]"
                table.add_row(
                    provider,
                    p.name,
                    status,
                    str(p.requests_made),
                    str(p.consecutive_errors),
                )

    def action_back(self) -> None:
        self.app.pop_screen()
