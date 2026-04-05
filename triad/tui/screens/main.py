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
        action_name = event.button.id
        if action_name in ("solo", "critic", "delegate", "history", "accounts"):
            self.run_action(action_name)

    async def action_solo(self) -> None:
        import asyncio
        from pathlib import Path

        from triad.core.accounts.manager import AccountManager
        from triad.core.modes.solo import SoloMode
        from triad.core.storage.ledger import Ledger

        config_obj = self.app.triad_config  # type: ignore[attr-defined]

        db_path = config_obj.db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        ledger = Ledger(db_path=db_path)
        await ledger.initialize()

        mgr = AccountManager(profiles_dir=config_obj.profiles_dir)
        mgr.discover()

        solo = SoloMode(ledger=ledger, account_manager=mgr)
        await solo.pre_launch()

        exit_code = 1
        try:
            with self.app.suspend():
                exit_code = await asyncio.to_thread(solo.launch, Path.cwd())
        finally:
            await solo.post_launch(exit_code)
            await ledger.close()

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

    def on_mount(self) -> None:
        import os
        from triad.core.policy import PolicyGuard
        guard = PolicyGuard()
        warnings = guard.check_environment(dict(os.environ))
        for w in warnings:
            self.notify(w, severity="warning", timeout=10)

    def action_quit(self) -> None:
        self.app.exit()
