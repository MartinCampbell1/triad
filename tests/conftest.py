from pathlib import Path
import pytest


@pytest.fixture
def tmp_profiles(tmp_path: Path) -> Path:
    """Create a temporary profiles directory with fake provider profiles."""
    profiles = tmp_path / "profiles"

    # Claude: 1 account
    claude_home = profiles / "claude" / "acc1" / "home" / ".claude"
    claude_home.mkdir(parents=True)
    (claude_home / "settings.json").write_text("{}")

    # Codex: 3 accounts
    for i in range(1, 4):
        codex_dir = profiles / "codex" / f"acc{i}"
        codex_dir.mkdir(parents=True)
        (codex_dir / "auth.json").write_text("{}")
        (codex_dir / "config.toml").write_text("")

    # Gemini: 2 accounts
    for i in range(1, 3):
        gemini_home = profiles / "gemini" / f"acc{i}" / "home" / ".config" / "gemini"
        gemini_home.mkdir(parents=True)
        (gemini_home / "settings.json").write_text("{}")

    return profiles


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a path for a temporary SQLite database."""
    return tmp_path / "triad.db"


@pytest.fixture
def tmp_artifacts(tmp_path: Path) -> Path:
    """Return a path for temporary artifact storage."""
    d = tmp_path / "artifacts"
    d.mkdir()
    return d
