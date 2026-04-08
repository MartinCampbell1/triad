import json
from pathlib import Path

import pytest

from triad.desktop.bridge import DesktopRuntime, bridge


@pytest.mark.asyncio
async def test_desktop_runtime_export_archive_and_import_roundtrip(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    export_path = tmp_path / "session-export.json"

    runtime = DesktopRuntime()
    await runtime.initialize()
    try:
        await runtime.open_project(str(project_dir))
        session = await runtime.create_session(
            str(project_dir), "critic", "claude", "Export me"
        )
        session_id = session["id"]
        ledger = await runtime.ledger()
        await ledger.append_event(
            session_id,
            "user.message",
            {"content": "Roundtrip context"},
            provider="claude",
            role="user",
            content="Roundtrip context",
        )
        await ledger.append_event(
            session_id,
            "message_finalized",
            {"content": "Roundtrip answer"},
            provider="claude",
            role="writer",
            content="Roundtrip answer",
        )

        exported = await runtime.export_session(
            session_id,
            format_name="archive",
            output_path=str(export_path),
        )

        assert exported["format"] == "archive"
        assert exported["path"] == str(export_path.resolve())
        archive = json.loads(export_path.read_text(encoding="utf-8"))
        assert archive["type"] == "triad_desktop_session_archive"
        assert archive["version"] == 1
        assert archive["session"]["title"] == "Export me"
        assert archive["session"]["source_session_id"] == session_id
        assert any(event["type"] == "message_finalized" for event in archive["events"])

        imported = await runtime.import_session(str(export_path))

        assert imported["session"]["id"] != session_id
        assert imported["session"]["title"] == "Export me"
        assert imported["session"]["project_path"] == str(project_dir.resolve())
        assert imported["session"]["status"] == "paused"
        assert imported["session"]["created_at"] == archive["session"]["created_at"]
        assert any(
            message["content"] == "Roundtrip context"
            for message in imported["messages"]
        )
        assert any(
            message["content"] == "Roundtrip answer" for message in imported["messages"]
        )

        projects = await runtime.list_projects()
        assert any(
            project["path"] == str(project_dir.resolve()) for project in projects
        )
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_import_dedupes_authoritative_message_replacements_by_message_id(
    tmp_path: Path,
):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    archive_path = tmp_path / "authoritative-archive.json"

    archive_path.write_text(
        json.dumps(
            {
                "type": "triad_desktop_session_archive",
                "version": 1,
                "exported_at": "2026-04-08T00:00:00Z",
                "session": {
                    "id": "source-session",
                    "source_session_id": "source-session",
                    "title": "Authoritative import",
                    "task": "Authoritative import",
                    "mode": "solo",
                    "status": "completed",
                    "provider": "claude",
                    "project_path": str(project_dir),
                    "created_at": "2026-04-08T00:00:00Z",
                    "updated_at": "2026-04-08T00:00:00Z",
                },
                "project": {
                    "path": str(project_dir),
                    "name": project_dir.name,
                    "git_root": str(project_dir),
                },
                "events": [
                    {
                        "session_id": "source-session",
                        "seq": 1,
                        "type": "message_finalized",
                        "provider": "claude",
                        "role": "assistant",
                        "timestamp": "2026-04-08T00:00:00Z",
                        "data": {
                            "content": "draft reply",
                            "message_id": "msg-1",
                        },
                    },
                    {
                        "session_id": "source-session",
                        "seq": 2,
                        "type": "message_finalized",
                        "provider": "claude",
                        "role": "assistant",
                        "timestamp": "2026-04-08T00:00:01Z",
                        "data": {
                            "content": "final reply",
                            "message_id": "msg-1",
                            "authoritative": True,
                        },
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    runtime = DesktopRuntime()
    await runtime.initialize()
    try:
        imported = await runtime.import_session(str(archive_path))
        assistant_messages = [
            message
            for message in imported["messages"]
            if message["role"] == "assistant"
        ]
        assert len(assistant_messages) == 1
        assert assistant_messages[0]["content"] == "final reply"
        assert imported["session"]["message_count"] == 1
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_import_normalizes_aliased_stream_event_types(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    archive_path = tmp_path / "aliased-archive.json"

    archive_path.write_text(
        json.dumps(
            {
                "type": "triad_desktop_session_archive",
                "version": 1,
                "exported_at": "2026-04-08T00:00:00Z",
                "session": {
                    "id": "source-session",
                    "source_session_id": "source-session",
                    "title": "Aliased import",
                    "task": "Aliased import",
                    "mode": "solo",
                    "status": "completed",
                    "provider": "claude",
                    "project_path": str(project_dir),
                    "created_at": "2026-04-08T00:00:00Z",
                    "updated_at": "2026-04-08T00:00:00Z",
                },
                "project": {
                    "path": str(project_dir),
                    "name": project_dir.name,
                    "git_root": str(project_dir),
                },
                "events": [
                    {
                        "session_id": "source-session",
                        "seq": 1,
                        "type": "message_completed",
                        "provider": "claude",
                        "role": "assistant",
                        "timestamp": "2026-04-08T00:00:00Z",
                        "data": {
                            "content": "aliased reply",
                        },
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    runtime = DesktopRuntime()
    await runtime.initialize()
    try:
        imported = await runtime.import_session(str(archive_path))
        assistant_messages = [
            message
            for message in imported["messages"]
            if message["role"] == "assistant"
        ]
        assert len(assistant_messages) == 1
        assert assistant_messages[0]["content"] == "aliased reply"
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_desktop_runtime_export_markdown_contains_transcript(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    export_path = tmp_path / "session-export.md"

    runtime = DesktopRuntime()
    await runtime.initialize()
    try:
        await runtime.open_project(str(project_dir))
        session = await runtime.create_session(
            str(project_dir), "solo", "claude", "Markdown export"
        )
        session_id = session["id"]
        ledger = await runtime.ledger()
        await ledger.append_event(
            session_id,
            "user.message",
            {"content": "Write the markdown report"},
            provider="claude",
            role="user",
            content="Write the markdown report",
        )
        await ledger.append_event(
            session_id,
            "message_finalized",
            {"content": "Here is the report body"},
            provider="claude",
            role="assistant",
            content="Here is the report body",
        )

        exported = await runtime.export_session(
            session_id,
            format_name="markdown",
            output_path=str(export_path),
        )

        assert exported["format"] == "markdown"
        markdown = export_path.read_text(encoding="utf-8")
        assert markdown.startswith("# Markdown export")
        assert "## Transcript" in markdown
        assert "Write the markdown report" in markdown
        assert "Here is the report body" in markdown
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_bridge_session_export_and_import_handlers_are_available(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    export_path = tmp_path / "bridge-session.json"

    runtime = DesktopRuntime()
    await runtime.initialize()
    previous_runtime = bridge.runtime
    bridge.runtime = runtime
    try:
        await runtime.open_project(str(project_dir))
        session = await runtime.create_session(
            str(project_dir), "delegate", "claude", "Bridge export"
        )

        exported = await bridge._handlers["session.export"](
            {
                "session_id": session["id"],
                "format": "archive",
                "path": str(export_path),
            }
        )
        imported = await bridge._handlers["session.import"]({"path": str(export_path)})

        assert exported["path"] == str(export_path.resolve())
        assert imported["session"]["id"] != session["id"]
        assert imported["session"]["title"] == "Bridge export"
    finally:
        bridge.runtime = previous_runtime
        await runtime.shutdown()
