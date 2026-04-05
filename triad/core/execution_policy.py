"""Role-aware execution policy for provider commands."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ExecutionPolicy:
    role: Literal["writer", "critic", "delegate", "solo"]
    sandbox: Literal["read_only", "workspace_write", "full_access"]

    @classmethod
    def writer(cls) -> ExecutionPolicy:
        return cls(role="writer", sandbox="workspace_write")

    @classmethod
    def critic(cls) -> ExecutionPolicy:
        return cls(role="critic", sandbox="read_only")

    @classmethod
    def delegate(cls) -> ExecutionPolicy:
        return cls(role="delegate", sandbox="workspace_write")

    @classmethod
    def solo(cls) -> ExecutionPolicy:
        return cls(role="solo", sandbox="full_access")
