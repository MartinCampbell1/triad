"""SQLite session/event ledger — canonical storage for Triad."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import aiosqlite


class Ledger:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
                title TEXT,
                project_path TEXT,
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
                run_id TEXT,
                provider TEXT,
                role TEXT,
                data_json TEXT,
                timestamp TEXT,
                ts REAL NOT NULL
            )
        """)
        await self._db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_session_seq ON events (session_id, seq)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_session_ts ON events (session_id, ts)"
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

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                path TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                git_root TEXT NOT NULL,
                last_opened_at REAL NOT NULL
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_projects_last_opened ON projects (last_opened_at DESC)"
        )

        await self._ensure_column("sessions", "title TEXT")
        await self._ensure_column("sessions", "project_path TEXT")
        await self._ensure_column("events", "run_id TEXT")
        await self._ensure_column("events", "provider TEXT")
        await self._ensure_column("events", "role TEXT")
        await self._ensure_column("events", "data_json TEXT")
        await self._ensure_column("events", "timestamp TEXT")
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def create_session(
        self,
        mode: str,
        task: str,
        config_json: str | None = None,
        *,
        title: str | None = None,
        project_path: str | None = None,
    ) -> str:
        now = time.time()
        sid = f"ts_{uuid.uuid4().hex[:12]}"
        await self._db.execute(
            """
            INSERT INTO sessions (
                id, mode, task, title, project_path, config_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (sid, mode, task, title, project_path, config_json, now, now),
        )
        await self._db.commit()
        return sid

    async def get_session(self, session_id: str) -> dict | None:
        rows = await self._db.execute_fetchall(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        return dict(rows[0]) if rows else None

    async def list_sessions(
        self,
        limit: int = 50,
        *,
        project_path: str | None = None,
    ) -> list[dict]:
        if project_path:
            rows = await self._db.execute_fetchall(
                """
                SELECT * FROM sessions
                WHERE project_path = ?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                (project_path, limit),
            )
        else:
            rows = await self._db.execute_fetchall(
                "SELECT * FROM sessions ORDER BY updated_at DESC, created_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(r) for r in rows]

    async def update_session_status(self, session_id: str, status: str) -> None:
        await self._db.execute(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            (status, time.time(), session_id),
        )
        await self._db.commit()

    async def update_session_title(self, session_id: str, title: str) -> None:
        await self._db.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, time.time(), session_id),
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
        await self._db.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def append_event(
        self,
        session_id: str,
        event_type: str,
        data: dict,
        *,
        provider: str | None = None,
        role: str | None = None,
        run_id: str | None = None,
        agent: str | None = None,
        content: str | None = None,
        artifact_id: str | None = None,
    ) -> int:
        now = time.time()
        cursor = await self._db.execute(
            """
            INSERT INTO events (
                session_id,
                seq,
                event_type,
                agent,
                content,
                artifact_id,
                run_id,
                provider,
                role,
                data_json,
                timestamp,
                ts
            ) VALUES (
                ?,
                (SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE session_id = ?),
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                session_id,
                session_id,
                event_type,
                agent,
                content,
                artifact_id,
                run_id,
                provider,
                role,
                json.dumps(data, ensure_ascii=False),
                time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
                now,
            ),
        )
        await self._db.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_events(self, session_id: str) -> list[dict]:
        rows = await self._db.execute_fetchall(
            "SELECT * FROM events WHERE session_id = ? ORDER BY seq", (session_id,)
        )
        return [dict(r) for r in rows]

    async def get_session_events(self, session_id: str, limit: int = 500) -> list[dict]:
        rows = await self._db.execute_fetchall(
            """
            SELECT *
            FROM events
            WHERE session_id = ?
            ORDER BY seq ASC
            LIMIT ?
            """,
            (session_id, limit),
        )
        events: list[dict] = []
        for row in rows:
            data_json = row["data_json"]
            data = {}
            if data_json:
                try:
                    data = json.loads(data_json)
                except json.JSONDecodeError:
                    data = {"raw": data_json}
            elif row["content"]:
                data = {"content": row["content"]}
            events.append(
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "seq": row["seq"],
                    "run_id": row["run_id"],
                    "type": row["event_type"],
                    "provider": row["provider"],
                    "role": row["role"],
                    "agent": row["agent"],
                    "content": row["content"],
                    "artifact_id": row["artifact_id"],
                    "timestamp": row["timestamp"],
                    "ts": row["ts"],
                    "data": data,
                }
            )
        return events

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

    async def save_project(self, path: str, display_name: str, git_root: str) -> None:
        await self._db.execute(
            """
            INSERT INTO projects (path, display_name, git_root, last_opened_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                display_name = excluded.display_name,
                git_root = excluded.git_root,
                last_opened_at = excluded.last_opened_at
            """,
            (path, display_name, git_root, time.time()),
        )
        await self._db.commit()

    async def list_projects(self) -> list[dict]:
        rows = await self._db.execute_fetchall(
            """
            SELECT path, display_name, git_root, last_opened_at
            FROM projects
            ORDER BY last_opened_at DESC
            """
        )
        return [
            {
                "path": row["path"],
                "display_name": row["display_name"],
                "name": row["display_name"],
                "git_root": row["git_root"],
                "last_opened_at": row["last_opened_at"],
            }
            for row in rows
        ]

    async def _ensure_column(self, table: str, definition: str) -> None:
        column_name = definition.split()[0]
        rows = await self._db.execute_fetchall(f"PRAGMA table_info({table})")
        if any(row["name"] == column_name for row in rows):
            return
        await self._db.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
