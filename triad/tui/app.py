"""Triad Textual TUI application."""
from __future__ import annotations

from pathlib import Path

from textual.app import App

from triad.core.config import TriadConfig, load_config
from triad.tui.screens.main import MainScreen


class TriadApp(App):
    TITLE = "Triad"
    CSS = """
    Screen {
        align: center middle;
    }
    #banner {
        text-align: center;
        padding: 1 2;
    }
    Button {
        width: 50;
        margin: 0 2;
    }
    """

    def __init__(self, config: TriadConfig | None = None, initial_mode: str | None = None):
        super().__init__()
        config_path = Path.home() / ".triad" / "config.yaml"
        self.triad_config = config or load_config(config_path)
        self.initial_mode = initial_mode

    def on_mount(self) -> None:
        self.push_screen(MainScreen())
        if self.initial_mode:
            self.set_timer(0.1, lambda: self.query_one(MainScreen).run_action(f"action_{self.initial_mode}"))
