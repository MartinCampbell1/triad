from pathlib import Path

import pytest

from triad.desktop.bridge import DesktopRuntime


@pytest.mark.asyncio
async def test_desktop_runtime_app_state_returns_last_project_and_session(tmp_path: Path):
    runtime = DesktopRuntime()
    await runtime.initialize()
    try:
        await runtime.open_project(str(tmp_path))
        session = await runtime.create_session(str(tmp_path), "critic", "claude", "Restore me")

        state = await runtime.get_app_state()

        assert state["last_project"] == str(tmp_path.resolve())
        assert state["last_session_id"] == session["id"]
        assert state["projects"][0]["path"] == str(tmp_path.resolve())
        assert state["sessions"][0]["id"] == session["id"]
    finally:
        await runtime.shutdown()
