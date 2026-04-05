"""Abstract base for provider CLI adapters."""
from __future__ import annotations

import asyncio
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from triad.core.env import build_runtime_base_env
from triad.core.models import Profile

RATE_LIMIT_PATTERNS: tuple[str, ...] = (
    "resource has been exhausted",
    "rate limit",
    "quota exceeded",
    "429",
    "too many requests",
    "insufficient_quota",
    "overloaded",
)


def is_rate_limited(text: str) -> bool:
    lower = text.lower()
    return any(pat in lower for pat in RATE_LIMIT_PATTERNS)


@dataclass
class ExecutionResult:
    success: bool
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    rate_limited: bool


class ProviderAdapter(ABC):
    provider: str
    cli_name: str

    @abstractmethod
    def headless_command(self, prompt: str, **kwargs) -> list[str]:
        ...

    @abstractmethod
    def build_env(self, profile: Profile, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
        ...

    def interactive_command(self) -> list[str]:
        raise NotImplementedError(f"{self.provider} does not support interactive mode")

    async def execute(
        self,
        profile: Profile,
        prompt: str,
        workdir: Path,
        timeout: int = 1800,
        base_env: Mapping[str, str] | None = None,
        **kwargs,
    ) -> ExecutionResult:
        cmd = self.headless_command(prompt, **kwargs)
        env = self.build_env(profile, base_env)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workdir),
                env=env,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            return ExecutionResult(
                success=proc.returncode == 0,
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                timed_out=False,
                rate_limited=is_rate_limited(stdout + stderr),
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ExecutionResult(
                success=False, returncode=None, stdout="",
                stderr=f"Timeout after {timeout}s", timed_out=True, rate_limited=False,
            )
        except Exception as exc:
            return ExecutionResult(
                success=False, returncode=None, stdout="",
                stderr=str(exc), timed_out=False, rate_limited=False,
            )

    def run_interactive(self, profile: Profile, workdir: Path, base_env: Mapping[str, str] | None = None) -> int:
        cmd = self.interactive_command()
        env = self.build_env(profile, base_env)
        result = subprocess.run(cmd, cwd=str(workdir), env=env)
        return result.returncode
