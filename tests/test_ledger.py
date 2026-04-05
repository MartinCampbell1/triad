import pytest
from pathlib import Path
from triad.core.storage.ledger import Ledger


@pytest.fixture
async def ledger(tmp_db: Path):
    lg = Ledger(db_path=tmp_db)
    await lg.initialize()
    yield lg
    await lg.close()


async def test_create_session(ledger: Ledger):
    sid = await ledger.create_session(mode="critic", task="Fix auth bug")
    assert sid is not None
    assert isinstance(sid, str)
    assert sid.startswith("ts_")


async def test_get_session(ledger: Ledger):
    sid = await ledger.create_session(mode="critic", task="Fix auth bug")
    session = await ledger.get_session(sid)
    assert session is not None
    assert session["mode"] == "critic"
    assert session["task"] == "Fix auth bug"
    assert session["status"] == "running"


async def test_log_event(ledger: Ledger):
    sid = await ledger.create_session(mode="critic", task="test")
    await ledger.log_event(session_id=sid, event_type="provider.started", agent="claude/writer")
    events = await ledger.get_events(sid)
    assert len(events) == 1
    assert events[0]["event_type"] == "provider.started"
    assert events[0]["agent"] == "claude/writer"


async def test_log_multiple_events_ordered(ledger: Ledger):
    sid = await ledger.create_session(mode="critic", task="test")
    await ledger.log_event(session_id=sid, event_type="provider.started", agent="claude/writer")
    await ledger.log_event(session_id=sid, event_type="provider.finished", agent="claude/writer")
    events = await ledger.get_events(sid)
    assert len(events) == 2
    assert events[0]["seq"] < events[1]["seq"]


async def test_list_sessions(ledger: Ledger):
    await ledger.create_session(mode="critic", task="Task 1")
    await ledger.create_session(mode="delegate", task="Task 2")
    sessions = await ledger.list_sessions()
    assert len(sessions) == 2


async def test_update_session_status(ledger: Ledger):
    sid = await ledger.create_session(mode="critic", task="test")
    await ledger.update_session_status(sid, "completed")
    session = await ledger.get_session(sid)
    assert session["status"] == "completed"


async def test_store_artifact(ledger: Ledger):
    sid = await ledger.create_session(mode="critic", task="test")
    aid = await ledger.store_artifact(sid, kind="writer_output", content="some code here")
    assert aid is not None
    assert aid.startswith("ta_")
