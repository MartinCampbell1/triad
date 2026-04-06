"""Triad desktop backend bridge package."""

from __future__ import annotations

from typing import Any

__all__ = [
    "ClaudePTY",
    "EventMerger",
    "HooksListener",
    "JsonRpcBridge",
    "TerminalManager",
    "main",
]


def __getattr__(name: str) -> Any:
    if name in {"JsonRpcBridge", "main"}:
        from .bridge import JsonRpcBridge, main

        exports = {"JsonRpcBridge": JsonRpcBridge, "main": main}
        return exports[name]

    if name == "ClaudePTY":
        from .claude_pty import ClaudePTY

        return ClaudePTY

    if name == "EventMerger":
        from .event_merger import EventMerger

        return EventMerger

    if name == "HooksListener":
        from .hooks_listener import HooksListener

        return HooksListener

    if name == "TerminalManager":
        from .terminal_manager import TerminalManager

        return TerminalManager

    raise AttributeError(name)
