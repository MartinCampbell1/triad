"""Base mode interface and state machine."""
from __future__ import annotations
from enum import StrEnum


class ModeState(StrEnum):
    IDLE = "idle"
    CONFIGURING = "configuring"
    RUNNING = "running"
    INTERVENTION = "intervention"
    COMPLETED = "completed"
    FAILED = "failed"
