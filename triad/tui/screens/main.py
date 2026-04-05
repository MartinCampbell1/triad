"""Main screen — mode selector."""
from __future__ import annotations

import subprocess
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
        with self.app.suspend():
            subprocess.run(["claude"])

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
