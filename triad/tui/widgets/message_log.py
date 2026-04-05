"""Labeled message display widget."""
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog


class MessageLog(Widget):
    DEFAULT_CSS = """
    MessageLog {
        height: 1fr;
        border: solid $accent;
    }
    """

    def compose(self) -> ComposeResult:
        yield RichLog(id="log", highlight=True, markup=True)

    def add_message(self, provider: str, role: str, text: str) -> None:
        log = self.query_one("#log", RichLog)
        label = f"[bold cyan]\\[{provider}/{role}][/bold cyan]"
        log.write(f"\n{label} {'─' * 40}")
        log.write(text)

    def add_system(self, text: str) -> None:
        log = self.query_one("#log", RichLog)
        log.write(f"[dim]{text}[/dim]")

    def clear(self) -> None:
        self.query_one("#log", RichLog).clear()
