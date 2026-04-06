from __future__ import annotations

import contextlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

JsonValue = dict[str, Any]


def load_config_json(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def derive_title(content: str) -> str:
    title = " ".join(content.strip().split())
    if not title:
        return "New session"
    return title[:60]


def derive_fork_title(source_title: str) -> str:
    title = " ".join(source_title.strip().split()) or "Session"
    if title.lower().endswith("(fork)"):
        return title[:60]
    return f"{title[:52]} (fork)"


def format_ts(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return value
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(float(value)))
    except (TypeError, ValueError):
        return str(value)


def parse_ts(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    with contextlib.suppress(ValueError):
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    return None


def slugify(text: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    normalized = normalized.strip("-")
    return normalized[:48]


def normalize_import_path(raw_path: str) -> str:
    return str(Path(raw_path).expanduser().resolve())


def resolve_export_path(
    exports_dir: Path,
    title: str,
    session_id: str,
    format_name: str,
    output_path: str | None,
) -> Path:
    if output_path:
        return Path(output_path).expanduser().resolve()

    suffix = "json" if format_name == "archive" else "md"
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    slug = slugify(title) or session_id
    filename = f"{stamp}-{slug}-{session_id}.{suffix}"
    return (exports_dir / filename).resolve()


def normalize_import_events(archive: dict[str, Any]) -> list[dict[str, Any]]:
    raw_events = archive.get("events")
    if isinstance(raw_events, list) and raw_events:
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(raw_events, start=1):
            if not isinstance(item, dict):
                continue
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            normalized.append(
                {
                    "seq": int(item.get("seq") or index),
                    "type": str(item.get("type") or "system"),
                    "provider": str(item.get("provider")) if item.get("provider") else None,
                    "role": str(item.get("role")) if item.get("role") else None,
                    "agent": str(item.get("agent")) if item.get("agent") else None,
                    "run_id": str(item.get("run_id")) if item.get("run_id") else None,
                    "content": str(item.get("content")) if item.get("content") is not None else None,
                    "artifact_id": str(item.get("artifact_id")) if item.get("artifact_id") else None,
                    "timestamp": item.get("timestamp"),
                    "ts": item.get("ts"),
                    "data": data,
                }
            )
        return normalized

    raw_messages = archive.get("messages")
    if not isinstance(raw_messages, list):
        return []

    normalized_messages: list[dict[str, Any]] = []
    for index, item in enumerate(raw_messages, start=1):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "system")
        event_type = {
            "user": "user.message",
            "assistant": "message_finalized",
            "system": "system",
        }.get(role, "system")
        content = str(item.get("content") or "")
        attachments = _normalize_attachments(item.get("attachments"))
        data = {"content": content}
        if attachments:
            data["attachments"] = attachments
        normalized_messages.append(
            {
                "seq": index,
                "type": event_type,
                "provider": str(item.get("provider")) if item.get("provider") else None,
                "role": str(item.get("agent_role")) if item.get("agent_role") else None,
                "agent": str(item.get("provider")) if item.get("provider") else None,
                "run_id": None,
                "content": content,
                "artifact_id": None,
                "timestamp": item.get("timestamp"),
                "ts": item.get("timestamp"),
                "data": data,
            }
        )
    return normalized_messages


def build_session_messages(
    session_id: str,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("type", ""))
        data = event.get("data") or {}
        timestamp = format_ts(event.get("ts") or event.get("timestamp"))
        provider = event.get("provider")
        if event_type == "user.message":
            content = str(data.get("content") or event.get("content") or "")
            attachments = _normalize_attachments(data.get("attachments"))
            if content or attachments:
                messages.append(
                    {
                        "id": f"msg_user_{event['id']}",
                        "session_id": session_id,
                        "role": "user",
                        "content": content,
                        "provider": provider,
                        "timestamp": timestamp,
                        "attachments": attachments,
                    }
                )
        elif event_type == "message_finalized":
            content = str(data.get("content") or event.get("content") or "")
            if content:
                messages.append(
                    {
                        "id": f"msg_assistant_{event['id']}",
                        "session_id": session_id,
                        "role": "assistant",
                        "content": content,
                        "provider": provider,
                        "agent_role": event.get("role"),
                        "timestamp": timestamp,
                    }
                )
        elif event_type == "system":
            content = str(data.get("content") or event.get("content") or "")
            if content:
                messages.append(
                    {
                        "id": f"msg_system_{event['id']}",
                        "session_id": session_id,
                        "role": "system",
                        "content": content,
                        "provider": provider,
                        "timestamp": timestamp,
                    }
                )
        elif event_type == "tool_use":
            tool_name = str(data.get("tool") or "tool")
            messages.append(
                {
                    "id": f"msg_tool_{event['id']}",
                    "session_id": session_id,
                    "role": "system",
                    "content": f"Tool started: {tool_name}",
                    "provider": provider,
                    "timestamp": timestamp,
                }
            )
        elif event_type == "tool_result":
            tool_name = str(data.get("tool") or "tool")
            status = str(data.get("status") or ("failed" if data.get("success") is False else "completed"))
            messages.append(
                {
                    "id": f"msg_tool_result_{event['id']}",
                    "session_id": session_id,
                    "role": "system",
                    "content": f"Tool {status}: {tool_name}",
                    "provider": provider,
                    "timestamp": timestamp,
                }
            )
        elif event_type == "review_finding":
            severity = str(data.get("severity") or "P2")
            title = str(data.get("title") or "Finding")
            explanation = str(data.get("explanation") or "")
            messages.append(
                {
                    "id": f"msg_finding_{event['id']}",
                    "session_id": session_id,
                    "role": "system",
                    "content": f"[{severity}] {title}" + (f": {explanation}" if explanation else ""),
                    "provider": provider,
                    "timestamp": timestamp,
                }
            )
        elif event_type == "run_failed":
            messages.append(
                {
                    "id": f"msg_error_{event['id']}",
                    "session_id": session_id,
                    "role": "system",
                    "content": str(data.get("error") or event.get("content") or "Run failed"),
                    "provider": provider,
                    "timestamp": timestamp,
                }
            )
    return messages


def build_session_archive(
    session_id: str,
    *,
    runtime: Any,
    session_row: dict[str, Any],
    messages: list[dict[str, Any]],
    events: list[dict[str, Any]],
    count_messages: int,
    format_ts_fn: Any = format_ts,
) -> dict[str, Any]:
    config = load_config_json(session_row.get("config_json"))
    project_path = str(
        session_row.get("project_path")
        or config.get("project_path")
        or runtime.project_path
    )
    session_payload = {
        "id": runtime.session_id,
        "project_path": runtime.project_path,
        "title": runtime.title,
        "mode": runtime.mode,
        "status": str((session_row or {}).get("status") or runtime.state),
        "created_at": format_ts_fn((session_row or {}).get("created_at")),
        "updated_at": format_ts_fn((session_row or {}).get("updated_at")),
        "message_count": count_messages,
        "provider": runtime.provider,
        "source_session_id": session_id,
        "task": str(session_row.get("task") or runtime.title),
        "config": config,
    }
    return {
        "type": "triad_desktop_session_archive",
        "version": 1,
        "exported_at": format_ts_fn(time.time()),
        "session": session_payload,
        "project": {
            "path": project_path,
            "name": Path(project_path).name or "Project",
            "git_root": project_path,
        },
        "messages": messages,
        "events": events,
    }


def render_session_markdown(
    session_id: str,
    *,
    runtime: Any,
    session_row: dict[str, Any],
    messages: list[dict[str, Any]],
    format_ts_fn: Any = format_ts,
) -> str:
    session_data = {
        "title": runtime.title,
        "mode": runtime.mode,
        "provider": runtime.provider,
        "status": str((session_row or {}).get("status") or runtime.state),
        "project_path": str(session_row.get("project_path") or runtime.project_path),
    }
    lines = [
        f"# {session_data.get('title') or 'Session Export'}",
        "",
        f"- Session ID: {session_id}",
        f"- Mode: {session_data.get('mode') or 'solo'}",
        f"- Provider: {session_data.get('provider') or 'claude'}",
        f"- Status: {session_data.get('status') or 'completed'}",
        f"- Project: {session_data.get('project_path') or runtime.project_path}",
        f"- Exported At: {format_ts_fn(time.time())}",
        "",
        "## Transcript",
        "",
    ]

    if not messages:
        lines.append("_No transcript messages were recorded for this session._")
        return "\n".join(lines) + "\n"

    for message in messages:
        role = str(message.get("role") or "system").capitalize()
        provider = str(message.get("provider") or "").strip()
        agent_role = str(message.get("agent_role") or "").strip()
        badges = [badge for badge in (provider, agent_role) if badge]
        heading = role if not badges else f"{role} ({', '.join(badges)})"
        attachments = _normalize_attachments(message.get("attachments"))
        body = str(message.get("content") or "").rstrip() or "_Empty message_"
        if attachments:
            lines.extend(
                [
                    f"### {heading}",
                    "",
                    body,
                    "",
                    "Attachments:",
                ]
            )
            for attachment in attachments:
                name = str(attachment.get("name") or "attachment")
                path = str(attachment.get("path") or "").strip()
                kind = str(attachment.get("kind") or "file")
                suffix = f" ({kind})" if kind else ""
                lines.append(f"- {name}{suffix}" + (f" — `{path}`" if path else ""))
            lines.append("")
            continue
        lines.extend(
            [
                f"### {heading}",
                "",
                body,
                "",
            ]
        )

    return "\n".join(lines) + "\n"


async def restore_imported_events(
    ledger: Any,
    session_id: str,
    events: list[dict[str, Any]],
) -> None:
    if not events:
        return

    normalized_events = sorted(events, key=lambda event: int(event.get("seq", 0) or 0))
    if hasattr(ledger, "_events") and hasattr(ledger, "_seq"):
        next_event_id = len(ledger._events) + 1
        last_ts: float | None = None
        for index, event in enumerate(normalized_events, start=1):
            ts = parse_ts(event.get("ts")) or time.time()
            last_ts = ts
            ledger._events.append(
                {
                    "id": next_event_id,
                    "session_id": session_id,
                    "seq": index,
                    "event_type": str(event.get("type") or "system"),
                    "agent": str(event.get("agent")) if event.get("agent") else None,
                    "content": str(event.get("content")) if event.get("content") is not None else None,
                    "artifact_id": str(event.get("artifact_id")) if event.get("artifact_id") else None,
                    "run_id": str(event.get("run_id")) if event.get("run_id") else None,
                    "provider": str(event.get("provider")) if event.get("provider") else None,
                    "role": str(event.get("role")) if event.get("role") else None,
                    "data_json": json.dumps(event.get("data") or {}, ensure_ascii=False),
                    "timestamp": str(event.get("timestamp") or format_ts(ts)),
                    "ts": ts,
                }
            )
            next_event_id += 1
        ledger._seq[session_id] = len(normalized_events)
        if session_id in ledger._sessions and last_ts is not None:
            ledger._sessions[session_id]["updated_at"] = last_ts
        return

    db = getattr(ledger, "_db", None)
    if db is None:
        for event in normalized_events:
            await ledger.append_event(
                session_id,
                str(event.get("type") or "system"),
                dict(event.get("data") or {}),
                provider=str(event.get("provider")) if event.get("provider") else None,
                role=str(event.get("role")) if event.get("role") else None,
                run_id=str(event.get("run_id")) if event.get("run_id") else None,
                agent=str(event.get("agent")) if event.get("agent") else None,
                content=str(event.get("content")) if event.get("content") is not None else None,
                artifact_id=str(event.get("artifact_id")) if event.get("artifact_id") else None,
            )
        return

    for index, event in enumerate(normalized_events, start=1):
        ts = parse_ts(event.get("ts")) or time.time()
        await db.execute(
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                index,
                str(event.get("type") or "system"),
                str(event.get("agent")) if event.get("agent") else None,
                str(event.get("content")) if event.get("content") is not None else None,
                str(event.get("artifact_id")) if event.get("artifact_id") else None,
                str(event.get("run_id")) if event.get("run_id") else None,
                str(event.get("provider")) if event.get("provider") else None,
                str(event.get("role")) if event.get("role") else None,
                json.dumps(event.get("data") or {}, ensure_ascii=False),
                str(event.get("timestamp") or format_ts(ts)),
                ts,
            ),
        )
    await db.commit()


def _normalize_attachments(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


async def restore_imported_session_metadata(
    ledger: Any,
    *,
    session_id: str,
    mode: str,
    task: str,
    title: str,
    project_path: str,
    status: str,
    config_json: str,
    created_at: float,
    updated_at: float,
) -> None:
    if hasattr(ledger, "_sessions"):
        row = ledger._sessions.get(session_id)
        if row is None:
            return
        row.update(
            {
                "mode": mode,
                "task": task,
                "title": title,
                "project_path": project_path,
                "status": status,
                "config_json": config_json,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )
        return

    db = getattr(ledger, "_db", None)
    if db is None:
        await ledger.update_session_title(session_id, title)
        await ledger.update_session_status(session_id, status)
        return

    await db.execute(
        """
        UPDATE sessions
        SET mode = ?, task = ?, title = ?, project_path = ?, status = ?,
            config_json = ?, created_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            mode,
            task,
            title,
            project_path,
            status,
            config_json,
            created_at,
            updated_at,
            session_id,
        ),
    )
    await db.commit()
