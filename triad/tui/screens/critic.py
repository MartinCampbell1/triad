"""Critic mode TUI screen — writer + critic loop with intervention."""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    RichLog,
    Static,
)

from triad.core.accounts.manager import AccountManager
from triad.core.context.blackboard import Blackboard
from triad.core.modes.base import ModeState
from triad.core.modes.critic import CriticConfig, CriticMode
from triad.core.providers import get_adapter
from triad.core.storage.ledger import Ledger


class RoleSelectScreen(Screen):
    """Select writer and critic providers."""

    CSS = """
    RoleSelectScreen {
        align: center middle;
    }
    #role-container {
        width: 60;
        height: auto;
        border: solid $accent;
        padding: 1 2;
    }
    RadioSet {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="role-container"):
            yield Static("[bold]Select Roles[/bold]\n")
            yield Label("Writer (writes code):")
            with RadioSet(id="writer-select"):
                yield RadioButton("Claude", value=True, id="writer-claude")
                yield RadioButton("Codex", id="writer-codex")
                yield RadioButton("Gemini", id="writer-gemini")
            yield Label("")
            yield Label("Critic (reviews code):")
            with RadioSet(id="critic-select"):
                yield RadioButton("Codex", value=True, id="critic-codex")
                yield RadioButton("Claude", id="critic-claude")
                yield RadioButton("Gemini", id="critic-gemini")
            yield Label("")
            yield Button("Start Critic Mode", id="start", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            writer_set = self.query_one("#writer-select", RadioSet)
            critic_set = self.query_one("#critic-select", RadioSet)

            writer_map = {
                "writer-claude": "claude",
                "writer-codex": "codex",
                "writer-gemini": "gemini",
            }
            critic_map = {
                "critic-claude": "claude",
                "critic-codex": "codex",
                "critic-gemini": "gemini",
            }

            writer = "claude"
            critic = "codex"
            if writer_set.pressed_button:
                writer = writer_map.get(writer_set.pressed_button.id, "claude")
            if critic_set.pressed_button:
                critic = critic_map.get(critic_set.pressed_button.id, "codex")

            self.dismiss({"writer": writer, "critic": critic})


class CriticScreen(Screen):
    """Main critic mode screen — shows rounds and allows intervention."""

    BINDINGS = [
        ("escape", "stop", "Stop"),
        ("ctrl+s", "swap", "Swap Roles"),
    ]

    CSS = """
    #log-area {
        height: 1fr;
        border: solid $accent;
    }
    #input-area {
        height: 3;
        dock: bottom;
    }
    #status-bar {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        writer_provider: str = "claude",
        critic_provider: str = "codex",
    ):
        super().__init__()
        self.writer_provider = writer_provider
        self.critic_provider = critic_provider
        self._critic_mode: CriticMode | None = None
        self._running = False
        self._task_entered = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            f"[bold]Critic Mode[/bold] — Writer: [cyan]{self.writer_provider}[/cyan] | "
            f"Critic: [yellow]{self.critic_provider}[/yellow]",
            id="status-bar",
        )
        yield RichLog(id="log-area", highlight=True, markup=True)
        yield Input(
            placeholder="Enter task (or feedback between rounds)...",
            id="input-area",
        )
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log-area", RichLog)
        log.write(
            "[dim]Enter your task below and press Enter to start the critic loop.[/dim]"
        )
        log.write(
            f"[dim]Writer: {self.writer_provider} | Critic: {self.critic_provider}[/dim]"
        )
        log.write(
            "[dim]Between rounds: type feedback + Enter, or Esc to stop, Ctrl+S to swap.[/dim]"
        )
        self.query_one("#input-area", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.clear()

        log = self.query_one("#log-area", RichLog)

        if not self._task_entered:
            self._task_entered = True
            log.write(f"\n[bold green]Task:[/bold green] {text}")
            log.write("[dim]Initializing critic mode...[/dim]")
            await self._start_critic(text)
        else:
            if self._critic_mode and self._critic_mode.state == ModeState.INTERVENTION:
                log.write(f"\n[bold green]Your feedback:[/bold green] {text}")
                await self._run_next_round(user_feedback=text)

    async def _start_critic(self, task: str) -> None:
        log = self.query_one("#log-area", RichLog)

        try:
            config_obj = self.app.triad_config  # type: ignore[attr-defined]
            profiles_dir = config_obj.profiles_dir
            account_mgr = AccountManager(profiles_dir=profiles_dir)
            account_mgr.discover()

            writer_adapter = get_adapter(self.writer_provider)
            critic_adapter = get_adapter(self.critic_provider)

            writer_profile = account_mgr.get_next(self.writer_provider)
            critic_profile = account_mgr.get_next(self.critic_provider)

            if not writer_profile:
                log.write(
                    f"[bold red]ERROR:[/bold red] No available {self.writer_provider} profiles!"
                )
                return
            if not critic_profile:
                log.write(
                    f"[bold red]ERROR:[/bold red] No available {self.critic_provider} profiles!"
                )
                return

            db_path = config_obj.db_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
            ledger = Ledger(db_path=db_path)
            await ledger.initialize()

            blackboard = Blackboard(task=task)

            config = CriticConfig(
                writer_provider=self.writer_provider,
                critic_provider=self.critic_provider,
                max_rounds=config_obj.critic_max_rounds,
                workdir=Path.cwd(),
            )

            self._critic_mode = CriticMode(
                config=config,
                writer_adapter=writer_adapter,
                critic_adapter=critic_adapter,
                writer_profile=writer_profile,
                critic_profile=critic_profile,
                ledger=ledger,
                blackboard=blackboard,
            )

            session_id = await self._critic_mode.initialize()
            log.write(f"[dim]Session: {session_id}[/dim]")

            await self._run_next_round()

        except Exception as e:
            log.write(f"[bold red]ERROR:[/bold red] {e}")

    async def _run_next_round(self, user_feedback: str | None = None) -> None:
        log = self.query_one("#log-area", RichLog)
        mode = self._critic_mode

        if not mode or mode.state == ModeState.COMPLETED:
            log.write("\n[bold green]Critic loop complete![/bold green]")
            return

        self._running = True
        round_num = len(mode.rounds) + 1
        log.write(f"\n{'=' * 60}")
        log.write(f"[bold]Round {round_num}[/bold]")

        try:
            result = await mode.run_round(user_feedback=user_feedback)

            # Show writer output
            log.write(
                f"\n[bold cyan]\\[{result.writer_provider}/writer][/bold cyan] {'─' * 40}"
            )
            writer_text = result.writer_output
            if len(writer_text) > 3000:
                writer_text = writer_text[:3000] + "\n... (truncated)"
            log.write(writer_text)

            # Show critic output
            log.write(
                f"\n[bold yellow]\\[{result.critic_provider}/critic][/bold yellow] {'─' * 40}"
            )
            report = result.critic_report
            if report.lgtm:
                log.write("[bold green]LGTM — No issues found![/bold green]")
            else:
                if report.issues:
                    for issue in report.issues:
                        severity_color = {
                            "critical": "red",
                            "high": "red",
                            "medium": "yellow",
                            "low": "dim",
                        }.get(issue.severity, "white")
                        log.write(
                            f"  [{severity_color}][{issue.severity}][/{severity_color}] "
                            f"{issue.file}: {issue.summary}"
                        )
                        if issue.suggested_fix:
                            log.write(f"    [dim]Fix: {issue.suggested_fix}[/dim]")
                elif report.raw_text:
                    log.write(report.raw_text[:2000])

            # Show status
            if mode.state == ModeState.COMPLETED:
                log.write(f"\n[bold green]{'=' * 60}[/bold green]")
                if report.lgtm:
                    log.write("[bold green]Critic approved! Loop complete.[/bold green]")
                else:
                    log.write(
                        f"[bold yellow]Max rounds ({mode.config.max_rounds}) reached.[/bold yellow]"
                    )
            elif mode.state == ModeState.INTERVENTION:
                log.write(
                    f"\n[dim]Round {round_num} complete. "
                    f"Enter feedback + Enter to continue, or Esc to stop.[/dim]"
                )

        except Exception as e:
            log.write(f"[bold red]ERROR in round {round_num}:[/bold red] {e}")

        self._running = False

    def action_stop(self) -> None:
        log = self.query_one("#log-area", RichLog)
        log.write("\n[bold]Stopped by user.[/bold]")
        if self._critic_mode:
            self._critic_mode.state = ModeState.COMPLETED

    def action_swap(self) -> None:
        if self._critic_mode and not self._running:
            old_writer = self.writer_provider
            self.writer_provider = self.critic_provider
            self.critic_provider = old_writer
            log = self.query_one("#log-area", RichLog)
            log.write(
                f"\n[bold magenta]Roles swapped![/bold magenta] "
                f"Writer: [cyan]{self.writer_provider}[/cyan] | "
                f"Critic: [yellow]{self.critic_provider}[/yellow]"
            )
            self.query_one("#status-bar", Static).update(
                f"[bold]Critic Mode[/bold] — Writer: [cyan]{self.writer_provider}[/cyan] | "
                f"Critic: [yellow]{self.critic_provider}[/yellow]"
            )
