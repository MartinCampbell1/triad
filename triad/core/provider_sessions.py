"""Helpers for importing provider sessions and opening provider login flows."""
from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VALID_PROVIDERS = ("claude", "codex", "gemini")


def is_valid_provider(provider: str) -> bool:
    return provider in VALID_PROVIDERS


def provider_login_command(provider: str) -> list[str]:
    commands = {
        "codex": ["codex", "login"],
        "claude": ["claude", "auth", "login"],
        "gemini": ["gemini"],
    }
    if provider not in commands:
        raise ValueError(f"Unsupported provider: {provider}")
    return list(commands[provider])


def provider_source_dir(provider: str, home: Path | None = None) -> Path | None:
    base_home = (home or Path.home()).expanduser()
    if provider == "codex":
        return base_home / ".codex"
    if provider == "claude":
        return base_home / ".claude"
    if provider == "gemini":
        if (base_home / ".config" / "gemini").exists():
            return base_home / ".config" / "gemini"
        if (base_home / ".gemini").exists():
            return base_home / ".gemini"
        return None
    raise ValueError(f"Unsupported provider: {provider}")


def provider_has_logged_in_session(provider: str, home: Path | None = None) -> bool:
    base_home = (home or Path.home()).expanduser()
    if provider == "codex":
        source = base_home / ".codex"
        return (source / "auth.json").exists() or (source / "config.toml").exists()
    if provider == "claude":
        return (base_home / ".claude").exists()
    if provider == "gemini":
        return (base_home / ".config" / "gemini").exists() or (base_home / ".gemini").exists()
    raise ValueError(f"Unsupported provider: {provider}")


def _next_account_name(provider_dir: Path) -> str:
    existing = sorted(
        account_dir.name
        for account_dir in provider_dir.iterdir()
        if account_dir.is_dir() and account_dir.name.startswith("acc")
    )
    return f"acc{len(existing) + 1}"


def import_current_session(provider: str, profiles_dir: Path, home: Path | None = None) -> str:
    if not is_valid_provider(provider):
        raise ValueError(f"Unsupported provider: {provider}")

    base_home = (home or Path.home()).expanduser()
    provider_dir = profiles_dir / provider
    provider_dir.mkdir(parents=True, exist_ok=True)
    account_name = _next_account_name(provider_dir)
    destination = provider_dir / account_name

    if provider == "codex":
        source = base_home / ".codex"
        if not source.exists():
            raise FileNotFoundError(f"No active codex session found at {source}")
        shutil.copytree(source, destination)
        return account_name

    runtime_home = destination / "home"
    runtime_home.mkdir(parents=True, exist_ok=True)

    if provider == "claude":
        source = base_home / ".claude"
        if not source.exists():
            raise FileNotFoundError(f"No active claude session found at {source}")
        shutil.copytree(source, runtime_home / ".claude")
        return account_name

    if provider == "gemini":
        copied_any = False
        config_source = base_home / ".config" / "gemini"
        legacy_source = base_home / ".gemini"
        if config_source.exists():
            destination_path = runtime_home / ".config" / "gemini"
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(config_source, destination_path)
            copied_any = True
        if legacy_source.exists():
            shutil.copytree(legacy_source, runtime_home / ".gemini")
            copied_any = True
        if not copied_any:
            raise FileNotFoundError(
                f"No active gemini session found at {config_source} or {legacy_source}"
            )
        return account_name

    raise ValueError(f"Unsupported provider: {provider}")


def _create_terminal_command_script(command_str: str, working_dir: Path, *, provider: str) -> Path:
    script_body = "\n".join(
        [
            "#!/bin/zsh",
            f"cd {shlex.quote(str(working_dir))}",
            "clear",
            f'echo "[Triad] Starting {provider} login..."',
            command_str,
            "status=$?",
            'echo ""',
            'if [ "$status" -eq 0 ]; then',
            '  echo "[Triad] Login command finished."',
            "else",
            '  echo "[Triad] Login command exited with status $status."',
            "fi",
            'echo ""',
            'read "?Press Enter to close this window. "',
            "exit $status",
            "",
        ]
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=f"-triad-{provider}-login.command",
        delete=False,
        encoding="utf-8",
    ) as handle:
        handle.write(script_body)
        script_path = Path(handle.name)
    script_path.chmod(0o700)
    return script_path


def open_login_terminal(provider: str, cwd: Path | None = None) -> str:
    command = provider_login_command(provider)
    command_str = shlex.join(command)
    working_dir = (cwd or Path.home()).expanduser()

    if sys.platform == "darwin":
        script_path = _create_terminal_command_script(
            command_str,
            working_dir,
            provider=provider,
        )
        subprocess.Popen(["open", "-a", "Terminal", str(script_path)])
        return command_str

    subprocess.Popen(command, cwd=str(working_dir))
    return command_str
