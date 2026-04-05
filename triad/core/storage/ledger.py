"""SQLite session/event ledger — canonical storage for Triad."""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import aiosqlite


class Ledger:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.execute("PRAGMA foreign_keys=ON")

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                task TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                config_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                seq INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                agent TEXT,
                content TEXT,
                artifact_id TEXT,
                ts REAL NOT NULL
            )
        """)
        await self._db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_session_seq ON events (session_id, seq)"
        )

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                kind TEXT NOT NULL,
                path TEXT,
                content TEXT,
                metadata_json TEXT,
                created_at REAL NOT NULL
            )
        """)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def create_session(self, mode: str, task: str, config_json: str | None = None) -> str:
        now = time.time()
        sid = f"ts_{uuid.uuid4().hex[:12]}"
        await self._db.execute(
            "INSERT INTO sessions (id, mode, task, config_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (sid, mode, task, config_json, now, now),
        )
        await self._db.commit()
        return sid

    async def get_session(self, session_id: str) -> dict | None:
        rows = await self._db.execute_fetchall(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        return dict(rows[0]) if rows else None

    async def list_sessions(self, limit: int = 50) -> list[dict]:
        rows = await self._db.execute_fetchall(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in rows]

    async def update_session_status(self, session_id: str, status: str) -> None:
        await self._db.execute(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            (status, time.time(), session_id),
        )
        await self._db.commit()

    async def log_event(
        self, session_id: str, event_type: str,
        agent: str | None = None, content: str | None = None,
        artifact_id: str | None = None,
    ) -> int:
        now = time.time()
        cursor = await self._db.execute(
            """INSERT INTO events (session_id, seq, event_type, agent, content, artifact_id, ts)
            VALUES (?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE session_id = ?), ?, ?, ?, ?, ?)""",
            (session_id, session_id, event_type, agent, content, artifact_id, now),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_events(self, session_id: str) -> list[dict]:
        rows = await self._db.execute_fetchall(
            "SELECT * FROM events WHERE session_id = ? ORDER BY seq", (session_id,)
        )
        return [dict(r) for r in rows]

    async def store_artifact(
        self, session_id: str, kind: str,
        content: str | None = None, path: str | None = None,
        metadata_json: str | None = None,
    ) -> str:
        aid = f"ta_{uuid.uuid4().hex[:12]}"
        await self._db.execute(
            "INSERT INTO artifacts (id, session_id, kind, path, content, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (aid, session_id, kind, path, content, metadata_json, time.time()),
        )
        await self._db.commit()
        return aid
