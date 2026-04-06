import json
import sqlite3
from pathlib import Path

import pytest

from triad.desktop.search import SearchIndex


def _prepare_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                task TEXT NOT NULL,
                title TEXT,
                project_path TEXT,
                status TEXT NOT NULL,
                config_json TEXT,
                message_count INTEGER,
                provider TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE projects (
                path TEXT PRIMARY KEY,
                display_name TEXT,
                git_root TEXT,
                last_opened_at REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                agent TEXT,
                content TEXT,
                artifact_id TEXT,
                run_id TEXT,
                provider TEXT,
                role TEXT,
                data_json TEXT,
                timestamp TEXT,
                ts REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO sessions (
                id, mode, task, title, project_path, status, config_json, message_count, provider, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "sess_1",
                "solo",
                "task",
                "Fix desktop search",
                "/tmp/repo",
                "completed",
                None,
                4,
                "claude",
                0.0,
                0.0,
            ),
        )
        conn.execute(
            """
            INSERT INTO projects (
                path, display_name, git_root, last_opened_at
            ) VALUES (?, ?, ?, ?)
            """,
            ("/tmp/repo/projects/triad-search", "triad-search", "/tmp/repo", 0.0),
        )
        _insert_event(
            conn,
            session_id="sess_1",
            seq=1,
            event_type="user.message",
            content="Please review the architecture diagram attached.",
            data={
                "attachments": [
                    {
                        "name": "architecture.png",
                        "path": "/tmp/repo/architecture.png",
                        "kind": "image",
                        "mime_type": "image/png",
                    },
                    {
                        "name": "notes.txt",
                        "path": "/tmp/repo/notes.txt",
                        "kind": "file",
                        "mime_type": "text/plain",
                    },
                ]
            },
        )
        _insert_event(
            conn,
            session_id="sess_1",
            seq=2,
            event_type="message_finalized",
            content="Search panel should find this snippet quickly",
            data={},
        )
        _insert_event(
            conn,
            session_id="sess_1",
            seq=3,
            event_type="tool_use",
            content="Edited App.tsx",
            data={
                "tool": "edit",
                "input": {"file_path": "src/components/App.tsx"},
                "output": "updated",
            },
        )
        _insert_event(
            conn,
            session_id="sess_1",
            seq=4,
            event_type="review_finding",
            content="Typed search needs richer rows.",
            data={
                "title": "Typed search result",
                "file": "src/search.py",
                "line": 42,
                "severity": "P1",
                "explanation": "Search results need typed fields.",
            },
        )
        _insert_event(
            conn,
            session_id="sess_1",
            seq=5,
            event_type="diff_snapshot",
            content="Search parity patch",
            data={
                "diff_stat": " src/search.py | 12 +++-",
                "patch": "diff --git a/src/search.py b/src/search.py",
            },
        )
        _insert_event(
            conn,
            session_id="sess_1",
            seq=6,
            event_type="session.created",
            content="Fix desktop search session started",
            data={},
        )
        conn.commit()
    finally:
        conn.close()


def _insert_event(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    seq: int,
    event_type: str,
    content: str,
    data: dict[str, object],
) -> None:
    conn.execute(
        """
        INSERT INTO events (
            session_id, seq, event_type, agent, content, artifact_id, run_id, provider, role, data_json, timestamp, ts
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            seq,
            event_type,
            "claude",
            content,
            None,
            None,
            "claude",
            "assistant" if event_type != "user.message" else "user",
            json.dumps(data) if data else None,
            "2026-04-06T00:00:00",
            float(seq),
        ),
    )


def _results_by_type(results: list[dict[str, object]], artifact_type: str) -> list[dict[str, object]]:
    return [result for result in results if result.get("artifact_type") == artifact_type]


@pytest.mark.asyncio
async def test_search_index_returns_session_and_project_results(tmp_path: Path):
    db_path = tmp_path / "triad.db"
    _prepare_db(db_path)

    index = SearchIndex(db_path)
    await index.initialize()

    session_results = await index.search("Fix desktop search")
    assert _results_by_type(session_results, "session")
    session_result = _results_by_type(session_results, "session")[0]
    assert session_result["session_id"] == "sess_1"
    assert session_result["session_title"] == "Fix desktop search"
    assert session_result["project_path"] == "/tmp/repo"
    assert session_result["kind"] == "session"

    project_results = await index.search("triad-search")
    assert _results_by_type(project_results, "project")
    project_result = _results_by_type(project_results, "project")[0]
    assert project_result["title"] == "triad-search"
    assert project_result["project_path"] == "/tmp/repo/projects/triad-search"
    assert project_result["session_id"] is None


@pytest.mark.asyncio
async def test_search_index_returns_message_attachment_and_reply_results(tmp_path: Path):
    db_path = tmp_path / "triad.db"
    _prepare_db(db_path)

    index = SearchIndex(db_path)
    await index.initialize()
    results = await index.search("architecture")

    message_results = _results_by_type(results, "message")
    attachment_results = _results_by_type(results, "attachment")

    assert message_results
    assert attachment_results
    assert message_results[0]["attachment_count"] == 2
    assert attachment_results[0]["attachment_name"] == "architecture.png"
    assert attachment_results[0]["path"] == "/tmp/repo/architecture.png"
    assert "architecture" in message_results[0]["snippet"].lower()

    reply_results = await index.search("snippet")
    assert _results_by_type(reply_results, "reply")


@pytest.mark.asyncio
async def test_search_index_returns_file_change_finding_and_diff_results(tmp_path: Path):
    db_path = tmp_path / "triad.db"
    _prepare_db(db_path)

    index = SearchIndex(db_path)
    await index.initialize()

    file_change_results = await index.search("App.tsx")
    file_change = _results_by_type(file_change_results, "file_change")
    assert file_change
    assert file_change[0]["path"] == "src/components/App.tsx"
    assert file_change[0]["kind"] == "file_change"

    finding_results = await index.search("typed search")
    finding = _results_by_type(finding_results, "finding")
    assert finding
    assert finding[0]["severity"] == "P1"
    assert finding[0]["path"] == "src/search.py"
    assert finding[0]["line"] == 42

    diff_results = await index.search("Search parity")
    diff_snapshot = _results_by_type(diff_results, "diff_snapshot")
    assert diff_snapshot
    assert diff_snapshot[0]["diff_stat"] == "src/search.py | 12 +++-"
