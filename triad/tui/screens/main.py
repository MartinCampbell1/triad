"""Main screen — mode selector."""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static


class MainScreen(Screen):
    BINDINGS = [
        ("s", "solo", "Solo (Claude Code)"),
        ("c", "critic", "Critic"),
        ("d", "delegate", "Delegate"),
        ("h", "history", "History"),
        ("a", "accounts", "Accounts"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "[bold]Triad[/bold] — AI Orchestration Control Plane\n"
            f"[dim]Working directory: {Path.cwd()}[/dim]",
            id="banner",
        )
        yield Label("")
        yield Button("Solo — Full Claude Code", id="solo", variant="primary")
        yield Button("Critic — Writer + Reviewer", id="critic", variant="warning")
        yield Button("Delegate — Parallel Tasks", id="delegate", variant="success")
        yield Label("")
        yield Button("Session History", id="history")
        yield Button("Account Status", id="accounts")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "solo": self.action_solo,
            "critic": self.action_critic,
            "delegate": self.action_delegate,
            "history": self.action_history,
            "accounts": self.action_accounts,
        }
        handler = actions.get(event.button.id)
        if handler:
            handler()

    def action_solo(self) -> None:
        import asyncio
        from pathlib import Path
        from triad.core.modes.solo import SoloMode
        from triad.core.accounts.manager import AccountManager
        from triad.core.storage.ledger import Ledger

        async def _setup():
            db_path = Path.home() / ".triad" / "triad.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            ledger = Ledger(db_path=db_path)
            await ledger.initialize()
            profiles_dir = Path.home() / ".cli-profiles"
            mgr = AccountManager(profiles_dir=profiles_dir)
            mgr.discover()
            return SoloMode(ledger=ledger, account_manager=mgr), ledger

        # Run pre-launch async setup
        loop = asyncio.get_event_loop()
        solo, ledger = loop.run_until_complete(_setup())
        loop.run_until_complete(solo.pre_launch())

        # Suspend TUI and launch claude
        with self.app.suspend():
            exit_code = solo.launch(workdir=Path.cwd())

        # Post-launch logging
        loop.run_until_complete(solo.post_launch(exit_code))
        loop.run_until_complete(ledger.close())
        self.notify(f"Claude Code exited (code {exit_code}). Session logged.")

    def action_critic(self) -> None:
        from triad.tui.screens.critic import CriticScreen, RoleSelectScreen

        def on_roles_selected(roles: dict) -> None:
            self.app.push_screen(
                CriticScreen(
                    writer_provider=roles["writer"],
                    critic_provider=roles["critic"],
                )
            )

        self.app.push_screen(RoleSelectScreen(), callback=on_roles_selected)

    def action_delegate(self) -> None:
        from triad.tui.screens.delegate import DelegateScreen
        self.app.push_screen(DelegateScreen())

    def action_history(self) -> None:
        from triad.tui.screens.sessions import SessionsScreen
        self.app.push_screen(SessionsScreen())

    def action_accounts(self) -> None:
        from triad.tui.screens.accounts import AccountsScreen
        self.app.push_screen(AccountsScreen())

    def action_quit(self) -> None:
        self.app.exit()
