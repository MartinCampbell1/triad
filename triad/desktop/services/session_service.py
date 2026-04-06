from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from .attachments import format_attachments_for_prompt, summarize_attachment_names
from .session_transfer import (
    build_session_archive,
    build_session_messages,
    derive_fork_title,
    derive_title,
    format_ts,
    load_config_json,
    normalize_import_events,
    normalize_import_path,
    parse_ts,
    render_session_markdown,
    resolve_export_path,
    restore_imported_events,
    restore_imported_session_metadata,
)
from .terminal_host import build_terminal_host_metadata
from .timeline import build_session_timeline


SessionRuntimeFactory = Callable[..., Any]


async def create_session(
    runtime: Any,
    session_runtime_factory: SessionRuntimeFactory,
    project_path: str,
    mode: str,
    provider: str = "claude",
    title: str | None = None,
) -> dict[str, Any]:
    ledger = await runtime.ledger()
    normalized_project = str(Path(project_path).expanduser().resolve())
    session_title = title or f"New {mode} session"
    config_json = json.dumps(
        {
            "project_path": normalized_project,
            "provider": provider,
            "title": session_title,
        },
        ensure_ascii=False,
    )
    session_id = await ledger.create_session(
        mode=mode,
        task=session_title,
        config_json=config_json,
        title=session_title,
        project_path=normalized_project,
    )
    session_runtime = session_runtime_factory(
        session_id=session_id,
        project_path=normalized_project,
        mode=mode,
        provider=provider,
        title=session_title,
    )
    runtime._sessions[session_id] = session_runtime
    await ledger.append_event(
        session_id,
        "session.created",
        {
            "project_path": normalized_project,
            "provider": provider,
            "mode": mode,
            "title": session_title,
        },
        provider=provider,
    )
    session_row = await ledger.get_session(session_id)
    return build_session_payload(runtime, session_runtime, session_row=session_row)


async def list_sessions(runtime: Any, project_path: str | None = None) -> list[dict[str, Any]]:
    ledger = await runtime.ledger()
    target_project = str(Path(project_path).expanduser().resolve()) if project_path else None
    rows = await ledger.list_sessions(limit=1000, project_path=target_project)

    sessions: list[dict[str, Any]] = []
    for row in rows:
        config = load_config_json(row.get("config_json"))
        row_project = str(
            Path(row.get("project_path") or config.get("project_path") or os.getcwd()).expanduser().resolve()
        )
        runtime_state = runtime._sessions.get(str(row["id"]))
        if runtime_state is None:
            runtime_state = hydrate_session_runtime_from_row(runtime, runtime.session_runtime_factory, row, row_project)
        sessions.append(
            build_session_payload(
                runtime,
                runtime_state,
                session_row=row,
                message_count=await count_messages(runtime, row["id"]),
            )
        )
    return sessions


async def export_session(
    runtime: Any,
    session_id: str,
    *,
    format_name: str = "archive",
    output_path: str | None = None,
) -> dict[str, Any]:
    ledger = await runtime.ledger()
    row = await ledger.get_session(session_id)
    if row is None:
        raise ValueError(f"Unknown session: {session_id}")

    session_runtime = runtime._sessions.get(session_id) or await hydrate_session_runtime(runtime, runtime.session_runtime_factory, session_id)
    runtime._sessions[session_id] = session_runtime
    normalized_format = format_name.strip().lower() or "archive"
    target_path = resolve_export_path(
        runtime.config.exports_dir,
        session_runtime.title or row.get("title") or session_id,
        session_id,
        normalized_format,
        output_path,
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if normalized_format == "archive":
        events = await get_session_events(runtime, session_id, limit=5000)
        archive = build_session_archive(
            session_id,
            runtime=session_runtime,
            session_row=row,
            messages=build_session_messages(session_id, events),
            events=events,
            count_messages=await count_messages(runtime, session_id),
        )
        target_path.write_text(json.dumps(archive, indent=2, ensure_ascii=False) + "\n")
    elif normalized_format == "markdown":
        events = await get_session_events(runtime, session_id, limit=5000)
        markdown = render_session_markdown(
            session_id,
            runtime=session_runtime,
            session_row=row,
            messages=build_session_messages(session_id, events),
        )
        target_path.write_text(markdown, encoding="utf-8")
    else:
        raise ValueError(f"Unsupported export format: {format_name}")

    return {
        "status": "ok",
        "session_id": session_id,
        "format": normalized_format,
        "path": str(target_path),
    }


async def import_session(
    runtime: Any,
    session_runtime_factory: SessionRuntimeFactory,
    input_path: str,
) -> dict[str, Any]:
    source_path = Path(input_path).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError(f"Import file not found: {input_path}")

    try:
        archive = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid session archive: {exc}") from exc

    session_meta = archive.get("session")
    if not isinstance(session_meta, dict):
        raise ValueError("Invalid session archive: missing session payload")

    project_meta = archive.get("project") if isinstance(archive.get("project"), dict) else {}
    project_path = normalize_import_path(
        str(session_meta.get("project_path") or project_meta.get("path") or os.getcwd())
    )
    project_name = str(project_meta.get("name") or Path(project_path).name or "Imported Project")
    git_root = normalize_import_path(str(project_meta.get("git_root") or project_path))

    provider = str(session_meta.get("provider") or "claude")
    mode = str(session_meta.get("mode") or "solo")
    title = str(session_meta.get("title") or session_meta.get("task") or source_path.stem)
    task = str(session_meta.get("task") or title)
    original_status = str(session_meta.get("status") or "completed")
    imported_status = "paused" if original_status in {"active", "running"} else original_status
    session_config = load_config_json(session_meta.get("config") or session_meta.get("config_json"))
    session_config.update(
        {
            "project_path": project_path,
            "provider": provider,
            "title": title,
            "imported_from_path": str(source_path),
            "imported_at": format_ts(time.time()),
            "imported_original_status": original_status,
            "imported_source_session_id": session_meta.get("source_session_id") or session_meta.get("id"),
        }
    )
    config_json = json.dumps(session_config, ensure_ascii=False)
    events = normalize_import_events(archive)

    ledger = await runtime.ledger()
    await ledger.save_project(project_path, project_name, git_root)
    imported_session_id = await ledger.create_session(
        mode=mode,
        task=task,
        config_json=config_json,
        title=title,
        project_path=project_path,
    )
    await restore_imported_events(ledger, imported_session_id, events)

    created_at = parse_ts(session_meta.get("created_at")) or time.time()
    updated_at = parse_ts(session_meta.get("updated_at"))
    if updated_at is None and events:
        updated_at = parse_ts(events[-1].get("ts")) or time.time()
    updated_at = updated_at or created_at
    await restore_imported_session_metadata(
        ledger,
        session_id=imported_session_id,
        mode=mode,
        task=task,
        title=title,
        project_path=project_path,
        status=imported_status,
        config_json=config_json,
        created_at=created_at,
        updated_at=updated_at,
    )

    session_runtime = session_runtime_factory(
        session_id=imported_session_id,
        project_path=project_path,
        mode=mode,
        provider=provider,
        title=title,
        state=imported_status,
    )
    runtime._sessions[imported_session_id] = session_runtime
    hydrated = await get_session(runtime, imported_session_id)
    return {
        **hydrated,
        "project": {
            "path": project_path,
            "name": project_name,
            "git_root": git_root,
            "last_opened_at": format_ts(time.time()),
        },
        "path": str(source_path),
    }


async def fork_session(
    runtime: Any,
    session_runtime_factory: SessionRuntimeFactory,
    source_session_id: str,
    *,
    title: str | None = None,
) -> dict[str, Any]:
    ledger = await runtime.ledger()
    source_row = await ledger.get_session(source_session_id)
    if source_row is None:
        raise ValueError(f"Unknown session: {source_session_id}")

    source_runtime = runtime._sessions.get(source_session_id) or await hydrate_session_runtime(
        runtime,
        session_runtime_factory,
        source_session_id,
    )
    source_config = load_config_json(source_row.get("config_json"))
    source_title = str(source_row.get("title") or source_row.get("task") or source_runtime.title or "Session")
    source_mode = str(source_row.get("mode") or source_runtime.mode or "solo")
    source_provider = str(source_config.get("provider") or source_runtime.provider or "claude")
    source_project = str(
        Path(source_row.get("project_path") or source_config.get("project_path") or source_runtime.project_path)
        .expanduser()
        .resolve()
    )

    fork_title = title or derive_fork_title(source_title)
    fork_config = {
        **source_config,
        "project_path": source_project,
        "provider": source_provider,
        "title": fork_title,
        "fork_of_session_id": source_session_id,
        "fork_of_title": source_title,
        "forked_at": format_ts(time.time()),
    }
    fork_id = await ledger.create_session(
        mode=source_mode,
        task=fork_title,
        config_json=json.dumps(fork_config, ensure_ascii=False),
        title=fork_title,
        project_path=source_project,
    )
    fork_runtime = session_runtime_factory(
        session_id=fork_id,
        project_path=source_project,
        mode=source_mode,
        provider=source_provider,
        title=fork_title,
    )
    runtime._sessions[fork_id] = fork_runtime

    await ledger.append_event(
        fork_id,
        "session.created",
        {
            "project_path": source_project,
            "provider": source_provider,
            "mode": source_mode,
            "title": fork_title,
            "fork_of_session_id": source_session_id,
        },
        provider=source_provider,
    )

    copied_events = await get_session_events(runtime, source_session_id, limit=4000)
    for event in copied_events:
        event_type = str(event.get("type", "")).strip()
        if event_type not in {
            "user.message",
            "message_finalized",
            "system",
            "tool_use",
            "tool_result",
            "review_finding",
            "run_failed",
            "diff_snapshot",
        }:
            continue

        data = dict(event.get("data") or {})
        content = str(event.get("content") or "")
        if not data and content:
            data = {"error": content} if event_type == "run_failed" else {"content": content}

        await ledger.append_event(
            fork_id,
            event_type,
            data,
            provider=str(event.get("provider")) if event.get("provider") else None,
            role=str(event.get("role")) if event.get("role") else None,
            agent=str(event.get("agent")) if event.get("agent") else None,
            content=content or None,
            artifact_id=str(event.get("artifact_id")) if event.get("artifact_id") else None,
        )

    fork_note = f'Continued from "{source_title}"'
    await ledger.append_event(
        fork_id,
        "system",
        {
            "content": fork_note,
            "source_session_id": source_session_id,
        },
        provider=source_provider,
        content=fork_note,
    )
    await ledger.update_session_status(fork_id, "active")
    session_row = await ledger.get_session(fork_id)
    return build_session_payload(runtime, fork_runtime, session_row=session_row)


async def get_session(runtime: Any, session_id: str) -> dict[str, Any]:
    ledger = await runtime.ledger()
    row = await ledger.get_session(session_id)
    if row is None:
        raise ValueError(f"Unknown session: {session_id}")
    session_runtime = runtime._sessions.get(session_id) or await hydrate_session_runtime(
        runtime,
        runtime.session_runtime_factory,
        session_id,
    )
    runtime._sessions[session_id] = session_runtime
    session_payload = build_session_payload(
        runtime,
        session_runtime,
        session_row=row,
        message_count=await count_messages(runtime, session_id),
    )
    events = await get_session_events(runtime, session_id, limit=2000)
    return {
        "session": session_payload,
        "messages": build_session_messages(session_id, events),
        "timeline": await build_session_timeline(runtime, session_id),
    }


async def hydrate_session_runtime(
    runtime: Any,
    session_runtime_factory: SessionRuntimeFactory,
    session_id: str,
    project_path: str | None = None,
) -> Any:
    ledger = await runtime.ledger()
    row = await ledger.get_session(session_id)
    if row is None:
        if project_path is None:
            raise ValueError(f"Unknown session: {session_id}")
        return session_runtime_factory(
            session_id=session_id,
            project_path=str(Path(project_path).expanduser().resolve()),
            mode="solo",
            provider="claude",
            title="Recovered session",
        )
    resolved_project = str(
        Path(project_path or load_config_json(row.get("config_json")).get("project_path") or os.getcwd())
        .expanduser()
        .resolve()
    )
    return hydrate_session_runtime_from_row(runtime, session_runtime_factory, row, resolved_project)


def hydrate_session_runtime_from_row(
    runtime: Any,
    session_runtime_factory: SessionRuntimeFactory,
    row: dict[str, Any],
    resolved_project: str,
) -> Any:
    config = load_config_json(row.get("config_json"))
    session_runtime = session_runtime_factory(
        session_id=str(row["id"]),
        project_path=resolved_project,
        mode=str(row.get("mode") or "solo"),
        provider=str(config.get("provider") or "claude"),
        title=str(row.get("title") or row.get("task") or config.get("title") or "Recovered session"),
        state=str(row.get("status") or "active"),
    )
    return session_runtime


async def count_events(runtime: Any, session_id: str) -> int:
    ledger = await runtime.ledger()
    count_events_fn = getattr(ledger, "count_events", None)
    if callable(count_events_fn):
        return int(await count_events_fn(session_id))
    db = getattr(ledger, "_db", None)
    if db is None:
        return 0
    rows = await db.execute_fetchall(
        "SELECT COUNT(*) AS count FROM events WHERE session_id = ?",
        (session_id,),
    )
    return int(rows[0]["count"]) if rows else 0


async def count_messages(runtime: Any, session_id: str) -> int:
    events = await get_session_events(runtime, session_id, limit=2000)
    if events:
        return sum(1 for event in events if event.get("type") in {"user.message", "message_finalized"})
    return await count_events(runtime, session_id)


async def get_session_events(runtime: Any, session_id: str, limit: int = 500) -> list[dict[str, Any]]:
    ledger = await runtime.ledger()
    get_session_events_fn = getattr(ledger, "get_session_events", None)
    if not callable(get_session_events_fn):
        return []
    return list(await get_session_events_fn(session_id, limit))


async def build_contextual_prompt(
    runtime: Any,
    session_id: str,
    latest_user_content: str,
    *,
    provider: str,
    has_live_context: bool,
    latest_attachments: list[dict[str, Any]] | None = None,
) -> str:
    attachment_block = format_attachments_for_prompt(latest_attachments or [])
    latest_message = latest_user_content.strip() or "Use the attached files as the primary context for this request."
    if has_live_context:
        return latest_message if not attachment_block else f"{latest_message}\n\n{attachment_block}"

    messages = build_session_messages(session_id, await get_session_events(runtime, session_id, limit=2000))
    history = [message for message in messages if message.get("role") in {"user", "assistant"}]
    if history and history[-1].get("role") == "user":
        last_content = str(history[-1].get("content") or "").strip()
        last_attachments = history[-1].get("attachments") if isinstance(history[-1].get("attachments"), list) else []
        if last_content == latest_user_content.strip() and len(last_attachments) == len(latest_attachments or []):
            history = history[:-1]
    if not history:
        return latest_message if not attachment_block else f"{latest_message}\n\n{attachment_block}"

    transcript_lines: list[str] = []
    budget = 12000
    used = 0
    for message in reversed(history[-24:]):
        content = " ".join(str(message.get("content") or "").split())
        attachments = [dict(item) for item in message.get("attachments", []) if isinstance(item, dict)]
        attachment_suffix = ""
        if attachments:
            attachment_names = ", ".join(str(attachment.get("name") or "attachment") for attachment in attachments[:3])
            attachment_suffix = f" [attachments: {attachment_names}]"
        if not content:
            if not attachment_suffix:
                continue
            content = "Attached context"
        if len(content) > 1600:
            content = content[:1600].rstrip() + "..."
        prefix = "User" if message.get("role") == "user" else "Assistant"
        line = f"{prefix}: {content}{attachment_suffix}"
        if transcript_lines and used + len(line) > budget:
            break
        transcript_lines.append(line)
        used += len(line)
    transcript_lines.reverse()
    if not transcript_lines:
        return latest_message if not attachment_block else f"{latest_message}\n\n{attachment_block}"

    return (
        "You are continuing an existing Triad desktop session.\n"
        f"The active provider is {provider}. Use the conversation history as context, "
        "then respond naturally to the latest user message.\n"
        "Do not restate the full history unless it is necessary.\n\n"
        "Conversation so far:\n"
        + "\n\n".join(transcript_lines)
        + "\n\nLatest user message:\n"
        + latest_message
        + (f"\n\n{attachment_block}" if attachment_block else "")
    )


def build_session_payload(
    runtime: Any,
    session_runtime: Any,
    *,
    session_row: dict[str, Any] | None = None,
    message_count: int = 0,
) -> dict[str, Any]:
    terminal_host = None
    manager = getattr(runtime, "_terminal_manager", None)
    linked_terminal_id = getattr(session_runtime, "linked_terminal_id", None)
    if manager is not None and linked_terminal_id:
        terminal_session = manager.get_session(linked_terminal_id)
        if terminal_session is not None:
            terminal_host = build_terminal_host_metadata(session_runtime, terminal_session.describe())
        else:
            terminal_host = build_terminal_host_metadata(session_runtime)
    elif linked_terminal_id:
        terminal_host = build_terminal_host_metadata(session_runtime)

    payload = {
        "id": session_runtime.session_id,
        "project_path": session_runtime.project_path,
        "title": session_runtime.title,
        "mode": session_runtime.mode,
        "status": str((session_row or {}).get("status") or session_runtime.state),
        "created_at": format_ts((session_row or {}).get("created_at")),
        "updated_at": format_ts((session_row or {}).get("updated_at")),
        "message_count": message_count,
        "provider": session_runtime.provider,
    }
    if terminal_host is not None:
        payload["terminal_host"] = terminal_host
    return payload


def search_memory(ledger: Any, query: str, limit: int) -> list[dict[str, Any]]:
    needle = query.casefold()
    results: list[dict[str, Any]] = []
    for event in reversed(ledger._events):
        content = str(event.get("content") or "")
        if not content:
            continue
        index = content.casefold().find(needle)
        if index < 0:
            continue
        session = ledger._sessions.get(str(event.get("session_id")), {})
        snippet = highlight_snippet(content, index, len(query))
        results.append(
            {
                "event_id": int(event["id"]),
                "session_id": str(event["session_id"]),
                "session_title": str(session.get("title") or session.get("task") or "Session"),
                "project_path": str(session.get("project_path") or ""),
                "snippet": snippet,
            }
        )
        if len(results) >= limit:
            break
    return results


def highlight_snippet(content: str, start: int, length: int) -> str:
    prefix_start = max(0, start - 48)
    suffix_end = min(len(content), start + length + 72)
    prefix = content[prefix_start:start]
    match = content[start : start + length]
    suffix = content[start + length : suffix_end]
    head = "..." if prefix_start > 0 else ""
    tail = "..." if suffix_end < len(content) else ""
    return f"{head}{prefix}<mark>{match}</mark>{suffix}{tail}"


def derive_title_from_input(content: str, attachments: list[dict[str, Any]]) -> str:
    if content.strip():
        return derive_title(content)
    return derive_title(summarize_attachment_names(attachments))
