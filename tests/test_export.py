import pytest
from pathlib import Path
from triad.core.storage.ledger import Ledger
from triad.core.export import export_session_jsonl, export_session_markdown


@pytest.fixture
async def ledger_with_data(tmp_db: Path):
    lg = Ledger(db_path=tmp_db)
    await lg.initialize()
    sid = await lg.create_session(mode="critic", task="Fix auth bug")
    await lg.log_event(sid, "provider.started", agent="claude/writer")
    await lg.log_event(sid, "provider.finished", agent="claude/writer", content="def fix(): pass")
    await lg.log_event(sid, "provider.started", agent="codex/critic")
    await lg.log_event(sid, "provider.finished", agent="codex/critic", content="LGTM")
    yield lg, sid
    await lg.close()


async def test_export_jsonl(ledger_with_data, tmp_path: Path):
    ledger, sid = ledger_with_data
    output = tmp_path / "export.jsonl"
    result = await export_session_jsonl(ledger, sid, output)
    assert result.exists()
    lines = result.read_text().strip().split("\n")
    assert len(lines) == 5  # 1 session + 4 events


async def test_export_markdown(ledger_with_data, tmp_path: Path):
    ledger, sid = ledger_with_data
    output = tmp_path / "export.md"
    result = await export_session_markdown(ledger, sid, output)
    assert result.exists()
    text = result.read_text()
    assert "Fix auth bug" in text
    assert "claude/writer" in text
    assert "codex/critic" in text
