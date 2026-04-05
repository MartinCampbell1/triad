import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from triad.core.modes.solo import SoloMode
from triad.core.accounts.manager import AccountManager
from triad.core.storage.ledger import Ledger


@pytest.fixture
async def solo_setup(tmp_db: Path, tmp_profiles: Path):
    ledger = Ledger(db_path=tmp_db)
    await ledger.initialize()
    mgr = AccountManager(profiles_dir=tmp_profiles)
    mgr.discover()
    mode = SoloMode(ledger=ledger, account_manager=mgr)
    yield mode, ledger
    await ledger.close()


async def test_pre_launch_creates_session(solo_setup):
    mode, ledger = solo_setup
    sid = await mode.pre_launch()
    assert sid is not None
    session = await ledger.get_session(sid)
    assert session["mode"] == "solo"
    assert session["status"] == "running"


async def test_post_launch_marks_completed(solo_setup):
    mode, ledger = solo_setup
    sid = await mode.pre_launch()
    await mode.post_launch(exit_code=0)
    session = await ledger.get_session(sid)
    assert session["status"] == "completed"


async def test_post_launch_marks_failed(solo_setup):
    mode, ledger = solo_setup
    await mode.pre_launch()
    await mode.post_launch(exit_code=1)
    session = await ledger.get_session(mode.session_id)
    assert session["status"] == "failed"
