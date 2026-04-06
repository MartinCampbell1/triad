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


async def test_log_event_seq_is_unique(ledger: Ledger):
    """Verify sequential events get unique seq numbers even if logged rapidly."""
    sid = await ledger.create_session(mode="test", task="seq test")
    for i in range(10):
        await ledger.log_event(session_id=sid, event_type=f"event_{i}")
    events = await ledger.get_events(sid)
    seqs = [e["seq"] for e in events]
    assert len(seqs) == 10
    assert len(set(seqs)) == 10  # All unique
    assert seqs == sorted(seqs)  # Monotonically increasing


async def test_append_event_round_trips_structured_data(ledger: Ledger):
    sid = await ledger.create_session(
        mode="solo",
        task="desktop chat",
        title="Desktop Chat",
        project_path="/tmp/project-a",
    )

    await ledger.append_event(
        sid,
        "text_delta",
        {"delta": "hello"},
        provider="claude",
        role="assistant",
        run_id="run_1",
    )

    session = await ledger.get_session(sid)
    events = await ledger.get_session_events(sid)

    assert session["title"] == "Desktop Chat"
    assert session["project_path"] == "/tmp/project-a"
    assert len(events) == 1
    assert events[0]["type"] == "text_delta"
    assert events[0]["provider"] == "claude"
    assert events[0]["role"] == "assistant"
    assert events[0]["run_id"] == "run_1"
    assert events[0]["data"] == {"delta": "hello"}


async def test_list_sessions_can_filter_by_project(ledger: Ledger):
    await ledger.create_session(mode="solo", task="a", project_path="/tmp/a")
    await ledger.create_session(mode="solo", task="b", project_path="/tmp/b")

    sessions = await ledger.list_sessions(project_path="/tmp/a")

    assert len(sessions) == 1
    assert sessions[0]["project_path"] == "/tmp/a"


async def test_save_and_list_projects(ledger: Ledger):
    await ledger.save_project("/tmp/project-a", "Project A", "/tmp/project-a")
    await ledger.save_project("/tmp/project-b", "Project B", "/tmp/project-b")

    projects = await ledger.list_projects()

    assert len(projects) == 2
    assert projects[0]["name"] in {"Project A", "Project B"}
    assert {project["path"] for project in projects} == {"/tmp/project-a", "/tmp/project-b"}
