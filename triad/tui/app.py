"""Triad Textual TUI application."""
from __future__ import annotations

from textual.app import App

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

    SCREENS = {"main": MainScreen}

    def on_mount(self) -> None:
        self.push_screen("main")
