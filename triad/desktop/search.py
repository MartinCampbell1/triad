"""Session search helpers for the desktop client."""
from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 3


class SearchIndex:
    """Lightweight search index over persisted desktop artifacts."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    async def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._search_sync, query, limit)

    def _initialize_sync(self) -> None:
        conn = self._connect()
        try:
            self._ensure_schema(conn)
            conn.commit()
        finally:
            conn.close()

    def _search_sync(self, query: str, limit: int) -> list[dict[str, Any]]:
        tokens = self._query_tokens(query)
        if not tokens:
            return []

        normalized = self._normalize_query(query)
        conn = self._connect()
        try:
            self._ensure_schema(conn)
            self._sync_events(conn)
            conn.commit()

            results: list[dict[str, Any]] = []
            results.extend(self._search_event_results(conn, normalized, tokens, max(limit * 4, limit)))
            results.extend(self._search_session_results(conn, tokens, limit))
            results.extend(self._search_project_results(conn, tokens, limit))

            deduped: list[dict[str, Any]] = []
            seen: set[str] = set()
            for row in sorted(
                results,
                key=lambda item: (
                    -float(item.get("score") or 0.0),
                    str(item.get("artifact_type") or ""),
                    str(item.get("title") or ""),
                    str(item.get("result_id") or ""),
                ),
            ):
                result_id = str(row.get("result_id") or "")
                if not result_id or result_id in seen:
                    continue
                seen.add(result_id)
                deduped.append(row)
                if len(deduped) >= limit:
                    break
            return deduped
        finally:
            conn.close()

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        version_row = conn.execute(
            "SELECT value FROM search_meta WHERE key = 'schema_version'"
        ).fetchone()
        current_version = int(version_row["value"]) if version_row else 0
        schema_row = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'events_fts'
            """
        ).fetchone()
        schema_sql = str(schema_row["sql"] or "").casefold() if schema_row else ""
        expected_tokens = (
            "event_id unindexed",
            "session_id unindexed",
            "session_title",
            "project_path",
            "event_type",
            "artifact_type",
            "kind",
            "provider",
            "role",
            "title",
            "content",
            "searchable_text",
        )
        needs_rebuild = not schema_sql or any(token not in schema_sql for token in expected_tokens)
        if current_version != SCHEMA_VERSION or needs_rebuild:
            conn.execute("DROP TABLE IF EXISTS events_fts")

        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
                event_id UNINDEXED,
                session_id UNINDEXED,
                session_title,
                project_path,
                event_type,
                artifact_type,
                kind,
                provider,
                role,
                title,
                content,
                searchable_text
            )
            """
        )

        if current_version != SCHEMA_VERSION or needs_rebuild:
            conn.execute("DELETE FROM search_meta WHERE key = 'indexed_event_id'")
            conn.execute(
                """
                INSERT INTO search_meta (key, value)
                VALUES ('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (str(SCHEMA_VERSION),),
            )

    def _sync_events(self, conn: sqlite3.Connection) -> None:
        try:
            rows = conn.execute(
                """
                SELECT
                    events.id AS event_id,
                    events.session_id AS session_id,
                    sessions.title AS session_title,
                    sessions.project_path AS project_path,
                    events.event_type AS event_type,
                    events.content AS content,
                    events.data_json AS data_json,
                    events.provider AS provider,
                    events.role AS role
                FROM events
                LEFT JOIN sessions ON sessions.id = events.session_id
                ORDER BY events.id ASC
                """
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                """
                SELECT
                    id AS event_id,
                    session_id,
                    event_type,
                    content,
                    data_json,
                    provider,
                    role
                FROM events
                ORDER BY id ASC
                """
            ).fetchall()

        conn.execute("DELETE FROM events_fts")
        insert_sql = """
            INSERT INTO events_fts (
                event_id,
                session_id,
                session_title,
                project_path,
                event_type,
                artifact_type,
                kind,
                provider,
                role,
                title,
                content,
                searchable_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for row in rows:
            event = dict(row)
            data = self._parse_data_json(event.get("data_json"))
            event_type = str(event.get("event_type") or "system")
            kind = self._event_kind(event_type, data)
            session_title = str(event.get("session_title") or "Session")
            project_path = str(event.get("project_path") or "")
            content = str(event.get("content") or "")
            provider = str(event.get("provider") or "")
            role = str(event.get("role") or "")
            title = self._event_index_title(event_type, content, data, session_title)
            searchable_text = self._build_searchable_text(
                session_title=session_title,
                project_path=project_path,
                event_type=event_type,
                kind=kind,
                title=title,
                content=content,
                data=data,
                provider=provider,
                role=role,
            )
            conn.execute(
                insert_sql,
                (
                    int(event["event_id"]),
                    str(event.get("session_id") or ""),
                    session_title,
                    project_path,
                    event_type,
                    kind,
                    kind,
                    provider,
                    role,
                    title,
                    content,
                    searchable_text,
                ),
            )

    def _search_event_results(
        self,
        conn: sqlite3.Connection,
        normalized_query: str,
        tokens: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT
                events_fts.event_id AS event_id,
                events_fts.session_id AS session_id,
                events_fts.session_title AS session_title,
                events_fts.project_path AS project_path,
                events_fts.event_type AS event_type,
                events.content AS content,
                events.data_json AS data_json,
                events_fts.provider AS provider,
                events_fts.role AS role,
                bm25(events_fts) AS rank,
                snippet(events_fts, 11, '<mark>', '</mark>', '...', 20) AS snippet
            FROM events_fts
            JOIN events ON events.id = events_fts.event_id
            WHERE events_fts MATCH ?
            ORDER BY rank ASC
            LIMIT ?
            """,
            (normalized_query, limit),
        ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            event = dict(row)
            data = self._parse_data_json(event.get("data_json"))
            session_title = str(event.get("session_title") or "Session")
            project_path = str(event.get("project_path") or "")
            event_type = str(event.get("event_type") or "system")
            kind = self._event_kind(event_type, data)
            base_score = max(1.0, 1000.0 - (float(event.get("rank") or 0.0) * 100.0))
            results.extend(
                self._event_artifacts(
                    event_id=int(event["event_id"]),
                    session_id=str(event["session_id"]),
                    session_title=session_title,
                    project_path=project_path,
                    event_type=event_type,
                    kind=kind,
                    content=str(event.get("content") or ""),
                    data=data,
                    provider=str(event.get("provider") or ""),
                    role=str(event.get("role") or ""),
                    snippet=str(event.get("snippet") or ""),
                    base_score=base_score,
                    tokens=tokens,
                )
            )
        return results

    def _search_session_results(self, conn: sqlite3.Connection, tokens: list[str], limit: int) -> list[dict[str, Any]]:
        try:
            rows = conn.execute("SELECT * FROM sessions").fetchall()
        except sqlite3.OperationalError:
            return []

        results: list[dict[str, Any]] = []
        for row in rows:
            session = dict(row)
            title = str(session.get("title") or session.get("task") or "Session")
            project_path = str(session.get("project_path") or "")
            searchable = " ".join(
                str(value)
                for value in (
                    title,
                    session.get("task") or "",
                    project_path,
                    session.get("mode") or "",
                    session.get("status") or "",
                    session.get("provider") or "",
                )
                if str(value).strip()
            )
            if not self._matches_tokens(searchable, tokens):
                continue

            score = self._score_text(searchable, tokens, boost=50.0)
            message_count = int(session.get("message_count") or 0)
            results.append(
                {
                    "result_id": f"session:{session['id']}",
                    "artifact_type": "session",
                    "kind": "session",
                    "event_type": "session",
                    "event_id": None,
                    "session_id": str(session["id"]),
                    "session_title": title,
                    "project_path": project_path,
                    "title": title,
                    "snippet": f"{str(session.get('mode') or 'solo').title()} session · {message_count} messages",
                    "provider": str(session.get("provider") or ""),
                    "score": score,
                }
            )
            if len(results) >= limit:
                break
        return results

    def _search_project_results(self, conn: sqlite3.Connection, tokens: list[str], limit: int) -> list[dict[str, Any]]:
        try:
            rows = conn.execute("SELECT * FROM projects").fetchall()
        except sqlite3.OperationalError:
            return []

        results: list[dict[str, Any]] = []
        for row in rows:
            project = dict(row)
            path = str(project.get("path") or "")
            title = str(project.get("display_name") or Path(path).name or "Project")
            searchable = " ".join(
                str(value)
                for value in (
                    title,
                    path,
                    project.get("git_root") or "",
                )
                if str(value).strip()
            )
            if not self._matches_tokens(searchable, tokens):
                continue

            score = self._score_text(searchable, tokens, boost=40.0)
            results.append(
                {
                    "result_id": f"project:{path}",
                    "artifact_type": "project",
                    "kind": "project",
                    "event_type": "project",
                    "event_id": None,
                    "session_id": None,
                    "session_title": title,
                    "project_path": path,
                    "title": title,
                    "snippet": str(project.get("git_root") or path),
                    "score": score,
                }
            )
            if len(results) >= limit:
                break
        return results

    def _event_artifacts(
        self,
        *,
        event_id: int,
        session_id: str,
        session_title: str,
        project_path: str,
        event_type: str,
        kind: str,
        content: str,
        data: dict[str, Any],
        provider: str,
        role: str,
        snippet: str,
        base_score: float,
        tokens: list[str],
    ) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []

        if event_type == "user.message":
            attachment_items = self._normalize_attachments(data.get("attachments"))
            artifacts.append(
                {
                    "result_id": f"event:{event_id}:message",
                    "artifact_type": "message",
                    "kind": kind,
                    "event_type": event_type,
                    "event_id": event_id,
                    "session_id": session_id,
                    "session_title": session_title,
                    "project_path": project_path,
                    "title": self._message_title(content, attachment_items),
                    "snippet": self._message_snippet(content, snippet, attachment_items),
                    "provider": provider,
                    "role": role,
                    "score": base_score + self._score_text(" ".join(self._attachment_search_text(attachment_items)), tokens, boost=15.0),
                    "attachment_count": len(attachment_items) or None,
                }
            )
            for index, attachment in enumerate(attachment_items, start=1):
                attachment_name = str(attachment.get("name") or attachment.get("path") or f"attachment-{index}")
                attachment_path = str(attachment.get("path") or "")
                attachment_text = " ".join(
                    value
                    for value in (
                        attachment_name,
                        attachment_path,
                        str(attachment.get("kind") or ""),
                        str(attachment.get("mime_type") or ""),
                        content,
                    )
                    if value
                )
                artifacts.append(
                    {
                        "result_id": f"event:{event_id}:attachment:{index}",
                        "artifact_type": "attachment",
                        "kind": "attachment",
                        "event_type": event_type,
                        "event_id": event_id,
                        "session_id": session_id,
                        "session_title": session_title,
                        "project_path": project_path,
                        "title": attachment_name,
                        "snippet": self._trim_excerpt(attachment_text),
                        "path": attachment_path or None,
                        "provider": provider,
                        "role": role,
                        "attachment_name": attachment_name,
                        "attachment_path": attachment_path or None,
                        "attachment_count": len(attachment_items),
                        "score": base_score + self._score_text(attachment_text, tokens, boost=35.0) + 5.0,
                    }
                )
            return artifacts

        if event_type == "message_finalized":
            artifacts.append(
                {
                    "result_id": f"event:{event_id}:reply",
                    "artifact_type": "reply",
                    "kind": kind,
                    "event_type": event_type,
                    "event_id": event_id,
                    "session_id": session_id,
                    "session_title": session_title,
                    "project_path": project_path,
                    "title": self._message_title(content, []),
                    "snippet": self._trim_excerpt(content or snippet),
                    "provider": provider,
                    "role": role,
                    "score": base_score + self._score_text(" ".join((content, snippet)), tokens, boost=10.0),
                }
            )
            return artifacts

        if event_type in {"tool_use", "tool_result"}:
            tool = str(data.get("tool") or "tool").strip() or "tool"
            input_data = data.get("input") if isinstance(data.get("input"), dict) else {}
            path = self._extract_path(input_data, data)
            is_file_change = tool.lower() in {"edit", "write"} and bool(path)
            artifact_type = "file_change" if is_file_change else ("command" if tool.lower() in {"bash", "shell", "terminal"} else "tool")
            title = path or tool
            snippet_text = self._tool_snippet(tool, data, content, snippet, path)
            artifacts.append(
                {
                    "result_id": f"event:{event_id}:{artifact_type}",
                    "artifact_type": artifact_type,
                    "kind": kind,
                    "event_type": event_type,
                    "event_id": event_id,
                    "session_id": session_id,
                    "session_title": session_title,
                    "project_path": project_path,
                    "title": title,
                    "snippet": snippet_text,
                    "path": path or None,
                    "provider": provider,
                    "role": role,
                    "tool": tool,
                    "score": base_score + self._score_text(" ".join((tool, title, snippet_text, path or "")), tokens, boost=12.0),
                }
            )
            return artifacts

        if event_type == "review_finding":
            title = str(data.get("title") or "Finding").strip() or "Finding"
            file_path = str(data.get("file") or "").strip()
            artifacts.append(
                {
                    "result_id": f"event:{event_id}:finding",
                    "artifact_type": "finding",
                    "kind": kind,
                    "event_type": event_type,
                    "event_id": event_id,
                    "session_id": session_id,
                    "session_title": session_title,
                    "project_path": project_path,
                    "title": title,
                    "snippet": self._trim_excerpt(str(data.get("explanation") or snippet or "")),
                    "path": file_path or None,
                    "line": data.get("line"),
                    "severity": str(data.get("severity") or "P2"),
                    "provider": provider,
                    "role": role,
                    "score": base_score + self._score_text(" ".join((title, file_path, str(data.get("explanation") or ""))), tokens, boost=20.0),
                }
            )
            return artifacts

        if event_type == "diff_snapshot":
            diff_stat = str(data.get("diff_stat") or "").strip()
            patch = str(data.get("patch") or content or "").strip()
            artifacts.append(
                {
                    "result_id": f"event:{event_id}:diff",
                    "artifact_type": "diff_snapshot",
                    "kind": kind,
                    "event_type": event_type,
                    "event_id": event_id,
                    "session_id": session_id,
                    "session_title": session_title,
                    "project_path": project_path,
                    "title": diff_stat or "Diff snapshot",
                    "snippet": self._trim_excerpt(diff_stat or patch or snippet),
                    "diff_stat": diff_stat or None,
                    "provider": provider,
                    "role": role,
                    "score": base_score + self._score_text(" ".join((diff_stat, patch, snippet)), tokens, boost=14.0),
                }
            )
            return artifacts

        if event_type == "terminal_output":
            artifacts.append(
                {
                    "result_id": f"event:{event_id}:terminal",
                    "artifact_type": "terminal",
                    "kind": kind,
                    "event_type": event_type,
                    "event_id": event_id,
                    "session_id": session_id,
                    "session_title": session_title,
                    "project_path": project_path,
                    "title": "Terminal output",
                    "snippet": self._trim_excerpt(snippet or content),
                    "provider": provider,
                    "role": role,
                    "score": base_score + self._score_text(" ".join((snippet, content)), tokens, boost=8.0),
                }
            )
            return artifacts

        if event_type == "session.created":
            artifacts.append(
                {
                    "result_id": f"event:{event_id}:session",
                    "artifact_type": "session",
                    "kind": kind,
                    "event_type": event_type,
                    "event_id": event_id,
                    "session_id": session_id,
                    "session_title": session_title,
                    "project_path": project_path,
                    "title": session_title,
                    "snippet": self._trim_excerpt(content or snippet or "Session created"),
                    "provider": provider,
                    "role": role,
                    "score": base_score + self._score_text(" ".join((session_title, project_path, content, snippet)), tokens, boost=18.0),
                }
            )
            return artifacts

        artifacts.append(
            {
                "result_id": f"event:{event_id}:system",
                "artifact_type": "system",
                "kind": kind,
                "event_type": event_type,
                "event_id": event_id,
                "session_id": session_id,
                "session_title": session_title,
                "project_path": project_path,
                "title": str(data.get("title") or "System notice"),
                "snippet": self._trim_excerpt(str(data.get("content") or content or snippet)),
                "provider": provider,
                "role": role,
                "score": base_score + self._score_text(" ".join((content, snippet, str(data.get("title") or ""), str(data.get("content") or ""))), tokens, boost=6.0),
            }
        )
        return artifacts

    @staticmethod
    def _trim_excerpt(value: str, limit: int = 160) -> str:
        compact = " ".join(value.split()).strip()
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3].rstrip() + "..."

    @staticmethod
    def _query_tokens(query: str) -> list[str]:
        return [token.casefold() for token in re.split(r"\s+", query.strip()) if token]

    @staticmethod
    def _score_text(text: str, tokens: list[str], boost: float = 0.0) -> float:
        if not text:
            return boost
        lowered = text.casefold()
        hits = sum(1 for token in tokens if token in lowered)
        if hits == 0:
            return boost
        exact = 10.0 if " ".join(tokens) in lowered else 0.0
        return boost + (hits * 8.0) + exact

    @staticmethod
    def _matches_tokens(text: str, tokens: list[str]) -> bool:
        lowered = text.casefold()
        return all(token in lowered for token in tokens)

    @staticmethod
    def _normalize_query(query: str) -> str:
        tokens = [token for token in re.split(r"\s+", query.strip()) if token]
        if not tokens:
            return ""
        return " ".join(f'"{token.replace(chr(34), "")}"' for token in tokens)

    @staticmethod
    def _parse_data_json(raw: Any) -> dict[str, Any]:
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _normalize_attachments(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        attachments: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                attachments.append(dict(item))
        return attachments

    @staticmethod
    def _attachment_search_text(attachments: list[dict[str, Any]]) -> list[str]:
        return [
            " ".join(
                part
                for part in (
                    str(attachment.get("name") or ""),
                    str(attachment.get("path") or ""),
                    str(attachment.get("kind") or ""),
                    str(attachment.get("mime_type") or ""),
                )
                if part
            )
            for attachment in attachments
        ]

    @staticmethod
    def _message_title(content: str, attachments: list[dict[str, Any]]) -> str:
        if content.strip():
            return SearchIndex._trim_excerpt(content, 72)
        if attachments:
            names = [
                str(attachment.get("name") or attachment.get("path") or "attachment")
                for attachment in attachments[:3]
            ]
            return ", ".join(names)
        return "Message"

    @staticmethod
    def _message_snippet(content: str, snippet: str, attachments: list[dict[str, Any]]) -> str:
        if content.strip():
            return SearchIndex._trim_excerpt(content)
        if attachments:
            names = ", ".join(
                str(attachment.get("name") or attachment.get("path") or "attachment")
                for attachment in attachments[:3]
            )
            return f"Attachments: {names}"
        return SearchIndex._trim_excerpt(snippet or "Message")

    @staticmethod
    def _extract_path(input_data: dict[str, Any], data: dict[str, Any]) -> str:
        for container in (input_data, data):
            for key in ("file_path", "path", "target_file", "file", "old_path", "new_path"):
                value = container.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    @staticmethod
    def _tool_snippet(tool: str, data: dict[str, Any], content: str, snippet: str, path: str) -> str:
        payload_parts = [tool]
        if path:
            payload_parts.append(path)
        if content.strip():
            payload_parts.append(content)
        if snippet.strip():
            payload_parts.append(snippet)
        if isinstance(data.get("output"), str) and data.get("output"):
            payload_parts.append(str(data.get("output")))
        return SearchIndex._trim_excerpt(" ".join(payload_parts))

    @staticmethod
    def _event_kind(event_type: str, data: dict[str, Any]) -> str:
        if event_type == "user.message":
            return "message"
        if event_type == "message_finalized":
            return "reply"
        if event_type in {"tool_use", "tool_result"}:
            tool = str(data.get("tool") or "").lower()
            if tool in {"edit", "write"}:
                return "file_change"
            if tool in {"bash", "shell", "terminal"}:
                return "command"
            return "tool"
        if event_type == "review_finding":
            return "finding"
        if event_type == "terminal_output":
            return "terminal"
        if event_type == "session.created":
            return "session"
        return "event"

    @staticmethod
    def _event_index_title(event_type: str, content: str, data: dict[str, Any], session_title: str) -> str:
        if event_type == "user.message":
            return SearchIndex._message_title(content, SearchIndex._normalize_attachments(data.get("attachments")))
        if event_type == "message_finalized":
            return SearchIndex._message_title(content, [])
        if event_type in {"tool_use", "tool_result"}:
            tool = str(data.get("tool") or "tool").strip() or "tool"
            input_data = data.get("input") if isinstance(data.get("input"), dict) else {}
            path = SearchIndex._extract_path(input_data, data)
            return path or tool
        if event_type == "review_finding":
            return str(data.get("title") or "Finding").strip() or "Finding"
        if event_type == "diff_snapshot":
            return str(data.get("diff_stat") or "Diff snapshot").strip() or "Diff snapshot"
        if event_type == "terminal_output":
            return "Terminal output"
        if event_type == "session.created":
            return session_title
        return str(data.get("title") or session_title or "System notice")

    @staticmethod
    def _build_searchable_text(
        *,
        session_title: str,
        project_path: str,
        event_type: str,
        kind: str,
        title: str,
        content: str,
        data: dict[str, Any],
        provider: str,
        role: str,
    ) -> str:
        tokens = [
            session_title,
            project_path,
            event_type,
            kind,
            title,
            provider,
            role,
            content,
            str(data.get("title") or ""),
            str(data.get("explanation") or ""),
            str(data.get("file") or data.get("path") or ""),
            str(data.get("tool") or ""),
            str(data.get("status") or ""),
            str(data.get("command") or data.get("query") or data.get("pattern") or ""),
            str(data.get("output") or ""),
            str(data.get("diff_stat") or ""),
            str(data.get("patch") or ""),
        ]
        attachments = SearchIndex._normalize_attachments(data.get("attachments"))
        for attachment in attachments:
            tokens.extend(
                [
                    str(attachment.get("name") or ""),
                    str(attachment.get("path") or ""),
                    str(attachment.get("kind") or ""),
                    str(attachment.get("mime_type") or ""),
                ]
            )
        input_data = data.get("input") if isinstance(data.get("input"), dict) else {}
        if isinstance(input_data, dict):
            for key in ("file_path", "path", "target_file", "file", "command", "cmd", "old_string", "new_string", "content"):
                tokens.append(str(input_data.get(key) or ""))
        return " ".join(token for token in tokens if token)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn
