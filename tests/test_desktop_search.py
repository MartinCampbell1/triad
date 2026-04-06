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
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
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
                id, mode, task, title, project_path, status, config_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sess_1", "solo", "task", "Fix desktop search", "/tmp/repo", "completed", None, 0.0, 0.0),
        )
        conn.execute(
            """
            INSERT INTO events (
                session_id, seq, event_type, agent, content, artifact_id, run_id, provider, role, data_json, timestamp, ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sess_1", 1, "message_finalized", "claude", "Search panel should find this snippet quickly", None, None, "claude", "assistant", None, "2026-04-06T00:00:00", 0.0),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_search_index_returns_snippet_and_session_metadata(tmp_path: Path):
    db_path = tmp_path / "triad.db"
    _prepare_db(db_path)

    index = SearchIndex(db_path)
    await index.initialize()
    results = await index.search("snippet")

    assert len(results) == 1
    assert results[0]["session_id"] == "sess_1"
    assert results[0]["session_title"] == "Fix desktop search"
    assert results[0]["project_path"] == "/tmp/repo"
    assert "<mark>snippet</mark>" in results[0]["snippet"].lower()
