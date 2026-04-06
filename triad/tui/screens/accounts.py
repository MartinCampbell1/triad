"""Account status TUI screen."""
from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static

from triad.core.account_diagnostics import build_account_diagnostics_snapshot
from triad.core.accounts.manager import AccountManager
from triad.core.provider_sessions import import_current_session, open_login_terminal


class AccountsScreen(Screen):
    BINDINGS = [
        ("escape", "back", "Back"),
        ("r", "reload", "Reload"),
    ]

    CSS = """
    #accounts-summary {
        padding: 0 1 1 1;
    }
    #account-actions {
        height: auto;
        padding: 0 1 1 1;
    }
    #account-actions Button {
        width: auto;
        min-width: 14;
        margin-right: 1;
    }
    DataTable { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("[bold]Accounts[/bold]")
        yield Static("", id="accounts-summary")
        with Horizontal(id="account-actions"):
            yield Button("Reload", id="reload", variant="primary")
            yield Button("Login Codex", id="login-codex")
            yield Button("Import Codex", id="import-codex")
            yield Button("Login Claude", id="login-claude")
            yield Button("Import Claude", id="import-claude")
            yield Button("Login Gemini", id="login-gemini")
            yield Button("Import Gemini", id="import-gemini")
        yield DataTable(id="accounts-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#accounts-table", DataTable)
        table.add_columns("Provider", "Account", "Status", "Requests", "Errors", "Cooldown")
        self.run_worker(self._reload_snapshot(), exclusive=True)

    async def _reload_snapshot(self) -> None:
        table = self.query_one("#accounts-table", DataTable)
        summary = self.query_one("#accounts-summary", Static)
        table.clear(columns=False)

        config = self.app.triad_config  # type: ignore[attr-defined]
        profiles_dir = config.profiles_dir
        mgr = AccountManager(
            profiles_dir=profiles_dir,
            cooldown_base=config.cooldown_base_sec,
        )
        mgr.discover()
        snapshot = build_account_diagnostics_snapshot(config, mgr)

        if not mgr.pools:
            summary.update(
                f"[dim]Profiles dir:[/dim] {profiles_dir}\n"
                "[yellow]No managed profiles found yet.[/yellow]"
            )
            table.add_row("—", "—", "No profiles found", "—", "—", "—")
            return

        provider_lines: list[str] = [
            f"[dim]Profiles dir:[/dim] {profiles_dir}",
        ]

        for provider in snapshot["providers_priority"]:
            provider_payload = snapshot["providers"].get(provider, {})
            source_ready = provider_payload.get("source_session_available")
            managed_count = provider_payload.get("managed_profile_count", 0)
            available_count = provider_payload.get("available_profile_count", 0)
            status = "[green]source ready[/green]" if source_ready else "[yellow]source missing[/yellow]"
            provider_lines.append(
                f"{provider}: {available_count}/{managed_count} available, {status}"
            )

            profiles = provider_payload.get("profiles", [])
            if not profiles:
                table.add_row(
                    provider,
                    "—",
                    "No managed profiles",
                    "—",
                    "—",
                    "—",
                )
                continue

            for profile in profiles:
                profile_status = (
                    "[green]Available[/green]"
                    if profile["available"]
                    else "[red]Cooldown[/red]"
                )
                table.add_row(
                    provider,
                    profile["name"],
                    profile_status,
                    str(profile["requests_made"]),
                    str(profile["errors"]),
                    str(profile["cooldown_remaining_sec"]),
                )

        summary.update("\n".join(provider_lines))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "reload":
            await self.action_reload()
            return
        if button_id.startswith("login-"):
            provider = button_id.removeprefix("login-")
            await self._open_login(provider)
            return
        if button_id.startswith("import-"):
            provider = button_id.removeprefix("import-")
            await self._import_session(provider)

    async def _open_login(self, provider: str) -> None:
        command = await asyncio.to_thread(open_login_terminal, provider)
        self.notify(
            f"Opened login flow for {provider}: {command}",
            severity="information",
        )

    async def _import_session(self, provider: str) -> None:
        config = self.app.triad_config  # type: ignore[attr-defined]
        try:
            account_name = await asyncio.to_thread(
                import_current_session,
                provider,
                config.profiles_dir,
            )
        except FileNotFoundError as exc:
            self.notify(str(exc), severity="error", timeout=8)
            return
        except Exception as exc:  # pragma: no cover - defensive UI path
            self.notify(f"Import failed: {exc}", severity="error", timeout=8)
            return

        self.notify(
            f"Imported {provider} session as {account_name}.",
            severity="information",
        )
        await self.action_reload()

    async def action_reload(self) -> None:
        await self._reload_snapshot()

    def action_back(self) -> None:
        self.app.pop_screen()
