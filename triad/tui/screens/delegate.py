"""Delegate mode TUI screen — parallel task dispatch."""
from __future__ import annotations

import asyncio
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
    OptionList,
    RichLog,
    Select,
    Static,
)

from triad.core.accounts.manager import AccountManager
from triad.core.modes.delegate import DelegateConfig, DelegateMode, DelegateTask
from triad.core.storage.ledger import Ledger
from triad.core.worktrees import WorktreeManager


class DelegateScreen(Screen):
    """Delegate mode — add tasks, select providers, run in parallel."""

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    CSS = """
    #tasks-area {
        height: auto;
        max-height: 50%;
        border: solid $accent;
        padding: 1;
    }
    #log-area {
        height: 1fr;
        border: solid $success;
    }
    #input-row {
        height: 3;
        dock: bottom;
    }
    .task-entry {
        height: 3;
    }
    """

    def __init__(self):
        super().__init__()
        self._tasks: list[DelegateTask] = []
        self._running = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("[bold]Delegate Mode[/bold] — Parallel Task Dispatch", id="title")
        yield RichLog(id="tasks-area", highlight=True, markup=True)
        yield RichLog(id="log-area", highlight=True, markup=True)
        yield Input(placeholder="Task prompt (then select provider)...", id="input-row")
        yield Footer()

    def on_mount(self) -> None:
        tasks_log = self.query_one("#tasks-area", RichLog)
        tasks_log.write("[dim]Add tasks: type prompt + Enter, then pick provider.[/dim]")
        tasks_log.write("[dim]Type 'run' to execute all tasks in parallel.[/dim]")
        tasks_log.write("[dim]Type 'clear' to reset task list.[/dim]")
        self.query_one("#input-row", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.clear()

        tasks_log = self.query_one("#tasks-area", RichLog)
        log = self.query_one("#log-area", RichLog)

        if text.lower() == "run":
            if not self._tasks:
                tasks_log.write("[yellow]No tasks added yet![/yellow]")
                return
            await self._run_all()
            return

        if text.lower() == "clear":
            self._tasks.clear()
            tasks_log.clear()
            tasks_log.write("[dim]Task list cleared. Add new tasks.[/dim]")
            return

        # Check if text ends with @provider
        provider = "codex"  # default
        if "@claude" in text:
            provider = "claude"
            text = text.replace("@claude", "").strip()
        elif "@gemini" in text:
            provider = "gemini"
            text = text.replace("@gemini", "").strip()
        elif "@codex" in text:
            provider = "codex"
            text = text.replace("@codex", "").strip()

        task = DelegateTask(prompt=text, provider=provider)
        self._tasks.append(task)
        idx = len(self._tasks)
        color_map = {"claude": "cyan", "codex": "yellow", "gemini": "green"}
        color = color_map.get(provider, "white")
        tasks_log.write(
            f"  [bold]{idx}.[/bold] [{color}][{provider}][/{color}] {text[:80]}"
        )

    async def _run_all(self) -> None:
        log = self.query_one("#log-area", RichLog)
        self._running = True

        log.write(f"\n[bold]Running {len(self._tasks)} tasks in parallel...[/bold]")

        try:
            profiles_dir = Path.home() / ".cli-profiles"
            account_mgr = AccountManager(profiles_dir=profiles_dir)
            account_mgr.discover()

            db_path = Path.home() / ".triad" / "triad.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            ledger = Ledger(db_path=db_path)
            await ledger.initialize()

            worktree_mgr = WorktreeManager(base_dir=Path.home() / ".triad" / "worktrees")

            config = DelegateConfig(
                tasks=list(self._tasks),
                timeout=1800,
                use_worktrees=True,
                repo_path=Path.cwd(),
            )

            def on_started(task: DelegateTask):
                profile_name = task.profile_used.name if task.profile_used else "?"
                log.write(f"  [cyan]▶[/cyan] [{task.provider}/{profile_name}] {task.prompt[:60]}...")

            def on_completed(task: DelegateTask):
                if task.status == "completed":
                    log.write(f"  [green]✓[/green] [{task.provider}] Done")
                elif task.status == "rate_limited":
                    log.write(f"  [yellow]⚠[/yellow] [{task.provider}] Rate limited")
                else:
                    stderr = task.result.stderr[:100] if task.result else "unknown"
                    log.write(f"  [red]✗[/red] [{task.provider}] Failed: {stderr}")

            mode = DelegateMode(
                config=config,
                account_manager=account_mgr,
                ledger=ledger,
                worktree_manager=worktree_mgr,
                on_task_started=on_started,
                on_task_completed=on_completed,
            )

            await mode.initialize()
            log.write(f"[dim]Session: {mode.session_id}[/dim]")

            results = await mode.run_all()

            log.write(f"\n[bold]{'━' * 40}[/bold]")
            completed = sum(1 for t in results if t.status == "completed")
            failed = sum(1 for t in results if t.status == "failed")
            log.write(f"[bold]Results: {completed} completed, {failed} failed[/bold]")

            for task in results:
                if task.result and task.result.stdout:
                    log.write(f"\n[bold cyan]\\[{task.provider}][/bold cyan] {'─' * 30}")
                    output = task.result.stdout
                    if len(output) > 2000:
                        output = output[:2000] + "\n... (truncated)"
                    log.write(output)

            await ledger.close()

        except Exception as e:
            log.write(f"[bold red]ERROR:[/bold red] {e}")

        self._running = False

    def action_back(self) -> None:
        if not self._running:
            self.app.pop_screen()
