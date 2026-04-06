"""Session search helpers for the desktop client."""
from __future__ import annotations

import asyncio
import re
import sqlite3
from pathlib import Path
from typing import Any


class SearchIndex:
    """Lightweight FTS5 index over persisted session events."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    async def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._search_sync, query, limit)

    def _initialize_sync(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
                    session_id UNINDEXED,
                    content
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS search_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _search_sync(self, query: str, limit: int) -> list[dict[str, Any]]:
        normalized = self._normalize_query(query)
        if not normalized:
            return []

        conn = self._connect()
        try:
            self._ensure_schema(conn)
            self._sync_events(conn)
            rows = conn.execute(
                """
                SELECT
                    events_fts.rowid AS event_id,
                    events_fts.session_id AS session_id,
                    sessions.title AS session_title,
                    sessions.project_path AS project_path,
                    snippet(events_fts, 1, '<mark>', '</mark>', '...', 20) AS snippet
                FROM events_fts
                LEFT JOIN sessions ON sessions.id = events_fts.session_id
                WHERE events_fts MATCH ?
                ORDER BY bm25(events_fts)
                LIMIT ?
                """,
                (normalized, limit),
            ).fetchall()
            return [
                {
                    "event_id": int(row["event_id"]),
                    "session_id": str(row["session_id"]),
                    "session_title": str(row["session_title"] or "Session"),
                    "project_path": str(row["project_path"] or ""),
                    "snippet": str(row["snippet"] or ""),
                }
                for row in rows
            ]
        finally:
            conn.close()

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
                session_id UNINDEXED,
                content
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

    def _sync_events(self, conn: sqlite3.Connection) -> None:
        try:
            row = conn.execute(
                "SELECT value FROM search_meta WHERE key = 'indexed_event_id'"
            ).fetchone()
            indexed_event_id = int(row["value"]) if row else 0
            events = conn.execute(
                """
                SELECT
                    id,
                    session_id,
                    COALESCE(NULLIF(content, ''), data_json, '') AS searchable_content
                FROM events
                WHERE id > ?
                ORDER BY id ASC
                """,
                (indexed_event_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            return

        last_seen = indexed_event_id
        for event in events:
            event_id = int(event["id"])
            content = str(event["searchable_content"] or "").strip()
            if content:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO events_fts (rowid, session_id, content)
                    VALUES (?, ?, ?)
                    """,
                    (event_id, str(event["session_id"]), content),
                )
            last_seen = max(last_seen, event_id)

        if last_seen != indexed_event_id:
            conn.execute(
                """
                INSERT INTO search_meta (key, value)
                VALUES ('indexed_event_id', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (str(last_seen),),
            )
            conn.commit()

    @staticmethod
    def _normalize_query(query: str) -> str:
        tokens = [token for token in re.split(r"\s+", query.strip()) if token]
        if not tokens:
            return ""
        return " ".join(f'"{token.replace(chr(34), "")}"' for token in tokens)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn
