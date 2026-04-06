import base64
import json
from pathlib import Path
import subprocess

import pytest

from triad.desktop.bridge import DesktopRuntime, bridge
from triad.desktop.services.attachments import materialize_attachments


def _create_git_repo(root: Path) -> Path:
    repo = root / "project"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
    return repo


@pytest.mark.asyncio
async def test_desktop_runtime_export_archive_and_import_roundtrip(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    export_path = tmp_path / "session-export.json"

    runtime = DesktopRuntime()
    await runtime.initialize()
    try:
        await runtime.open_project(str(project_dir))
        session = await runtime.create_session(str(project_dir), "critic", "claude", "Export me")
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
        assert any(message["content"] == "Roundtrip context" for message in imported["messages"])
        assert any(message["content"] == "Roundtrip answer" for message in imported["messages"])

        projects = await runtime.list_projects()
        assert any(project["path"] == str(project_dir.resolve()) for project in projects)
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
        session = await runtime.create_session(str(project_dir), "solo", "claude", "Markdown export")
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
async def test_desktop_runtime_get_session_exposes_typed_timeline(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    runtime = DesktopRuntime()
    await runtime.initialize()
    try:
        await runtime.open_project(str(project_dir))
        session = await runtime.create_session(str(project_dir), "critic", "claude", "Typed timeline")
        session_id = session["id"]
        ledger = await runtime.ledger()
        await ledger.append_event(
            session_id,
            "user.message",
            {"content": "Review the latest patch"},
            provider="claude",
            role="user",
            content="Review the latest patch",
        )
        await ledger.append_event(
            session_id,
            "tool_use",
            {
                "tool": "Read",
                "input": {"path": "desktop/src/App.tsx"},
                "status": "running",
            },
            provider="claude",
            role="writer",
        )
        await ledger.append_event(
            session_id,
            "review_finding",
            {
                "severity": "P1",
                "file": "desktop/src/App.tsx",
                "title": "Bridge fallback remains active",
                "explanation": "The app still tries to hydrate a mock state during boot.",
            },
            provider="codex",
            role="critic",
        )
        await ledger.append_event(
            session_id,
            "diff_snapshot",
            {
                "patch": "\n".join(
                    [
                        "diff --git a/desktop/src/App.tsx b/desktop/src/App.tsx",
                        "--- a/desktop/src/App.tsx",
                        "+++ b/desktop/src/App.tsx",
                        "@@ -1,1 +1,2 @@",
                        " line one",
                        "+line two",
                    ]
                ),
                "diff_stat": "1 file changed, 1 insertion(+)",
            },
            provider="claude",
            role="writer",
        )

        hydrated = await runtime.get_session(session_id)

        assert any(item["kind"] == "user_message" for item in hydrated["timeline"])
        assert any(
            item["kind"] == "tool_call" and item["tool"] == "Read"
            for item in hydrated["timeline"]
        )
        assert any(
            item["kind"] == "review_finding" and item["severity"] == "P1"
            for item in hydrated["timeline"]
        )
        assert any(
            item["kind"] == "diff_snapshot" and "desktop/src/App.tsx" in item["patch"]
            for item in hydrated["timeline"]
        )
        assert not any(message["content"].startswith("!tool:") for message in hydrated["messages"])
        assert not any(message["content"].startswith("!finding:") for message in hydrated["messages"])
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_desktop_runtime_compare_sessions_returns_divergence_rows(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    runtime = DesktopRuntime()
    await runtime.initialize()
    try:
        await runtime.open_project(str(project_dir))
        left = await runtime.create_session(str(project_dir), "solo", "claude", "Left session")
        right = await runtime.create_session(str(project_dir), "solo", "claude", "Right session")
        ledger = await runtime.ledger()

        for session_id in (left["id"], right["id"]):
            await ledger.append_event(
                session_id,
                "user.message",
                {"content": "Inspect the repository boot flow"},
                provider="claude",
                role="user",
                content="Inspect the repository boot flow",
            )

        await ledger.append_event(
            left["id"],
            "message_finalized",
            {"content": "Left branch kept the old fallback path."},
            provider="claude",
            role="assistant",
            content="Left branch kept the old fallback path.",
        )
        await ledger.append_event(
            right["id"],
            "message_finalized",
            {"content": "Right branch removed the fallback path."},
            provider="claude",
            role="assistant",
            content="Right branch removed the fallback path.",
        )
        await ledger.append_event(
            right["id"],
            "review_finding",
            {
                "severity": "P1",
                "file": "desktop/src/App.tsx",
                "title": "Fallback removed",
                "explanation": "The right branch exits boot on bridge failure.",
            },
            provider="codex",
            role="critic",
        )

        result = await runtime.compare_sessions(left["id"], right["id"])

        assert result["left_session"]["id"] == left["id"]
        assert result["right_session"]["id"] == right["id"]
        assert result["overview"]["shared_prefix_count"] == 1
        assert result["overview"]["left_counts"]["assistant_message"] == 1
        assert result["overview"]["right_counts"]["review_finding"] == 1
        assert result["rows"][0]["status"] == "same"
        assert result["rows"][1]["status"] == "different"
        assert result["rows"][2]["status"] == "right_only"
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_desktop_runtime_replay_session_returns_frames_and_markers(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    runtime = DesktopRuntime()
    await runtime.initialize()
    try:
        await runtime.open_project(str(project_dir))
        session = await runtime.create_session(str(project_dir), "critic", "claude", "Replay me")
        session_id = session["id"]
        ledger = await runtime.ledger()
        await ledger.append_event(
            session_id,
            "user.message",
            {"content": "Audit the latest desktop diff"},
            provider="claude",
            role="user",
            content="Audit the latest desktop diff",
        )
        await ledger.append_event(
            session_id,
            "tool_use",
            {
                "tool": "Read",
                "input": {"path": "desktop/src/App.tsx"},
                "status": "running",
            },
            provider="claude",
            role="writer",
        )
        await ledger.append_event(
            session_id,
            "message_finalized",
            {"content": "Replay confirms the bridge boot flow is fixed."},
            provider="claude",
            role="writer",
            content="Replay confirms the bridge boot flow is fixed.",
        )

        replay = await runtime.replay_session(session_id)

        assert replay["session"]["id"] == session_id
        assert replay["total_frames"] == 3
        assert replay["frames"][0]["summary"]["label"] == "User message"
        assert replay["frames"][1]["summary"]["label"] == "Read · running"
        assert replay["frames"][2]["counts"]["assistant_message"] == 1
        assert replay["markers"][2]["label"] == "Assistant message"
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_bridge_runtime_catalog_handlers_expose_models_modes_and_capabilities():
    capabilities = await bridge._handlers["capabilities.list"]({})
    models = await bridge._handlers["models.list"]({})
    modes = await bridge._handlers["modes.list"]({})

    assert capabilities["defaults"] == {
        "provider": "claude",
        "model": "claude-opus-4-6",
        "mode": "solo",
    }
    assert any(provider["id"] == "claude" for provider in capabilities["providers"])
    assert any(model["provider"] == "gemini" for model in capabilities["models"])
    assert any(mode["id"] == "delegate" for mode in capabilities["modes"])
    assert any(model["id"] == "gpt-5.4" for model in models["models"])
    assert any(mode["id"] == "brainstorm" for mode in modes["modes"])


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
        session = await runtime.create_session(str(project_dir), "delegate", "claude", "Bridge export")

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


@pytest.mark.asyncio
async def test_bridge_compare_and_replay_handlers_are_available(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    runtime = DesktopRuntime()
    await runtime.initialize()
    previous_runtime = bridge.runtime
    bridge.runtime = runtime
    try:
        await runtime.open_project(str(project_dir))
        left = await runtime.create_session(str(project_dir), "solo", "claude", "Compare left")
        right = await runtime.create_session(str(project_dir), "solo", "claude", "Compare right")
        ledger = await runtime.ledger()
        await ledger.append_event(
            left["id"],
            "user.message",
            {"content": "Compare me"},
            provider="claude",
            role="user",
            content="Compare me",
        )
        await ledger.append_event(
            right["id"],
            "user.message",
            {"content": "Compare me"},
            provider="claude",
            role="user",
            content="Compare me",
        )
        await ledger.append_event(
            right["id"],
            "system",
            {"title": "Note", "content": "Right only"},
            provider="claude",
            role="assistant",
            content="Right only",
        )

        compare_result = await bridge._handlers["session.compare"](
            {
                "left_session_id": left["id"],
                "right_session_id": right["id"],
            }
        )
        replay_result = await bridge._handlers["session.replay"]({"session_id": right["id"]})

        assert compare_result["overview"]["shared_prefix_count"] == 1
        assert replay_result["total_frames"] == 2
    finally:
        bridge.runtime = previous_runtime
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_session_replay_preserves_materialized_attachments(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    runtime = DesktopRuntime()
    await runtime.initialize()
    try:
        await runtime.open_project(str(project_dir))
        session = await runtime.create_session(str(project_dir), "solo", "claude", "Attachment replay")
        attachments = materialize_attachments(
            [
                {
                    "id": "att_inline",
                    "name": "context.txt",
                    "kind": "file",
                    "mime_type": "text/plain",
                    "content_base64": base64.b64encode(b"hello from attachment\n").decode("ascii"),
                }
            ],
            project_path=str(project_dir),
            artifacts_dir=runtime.config.artifacts_dir,
            session_id=session["id"],
        )
        ledger = await runtime.ledger()
        await ledger.append_event(
            session["id"],
            "user.message",
            {"content": "", "attachments": attachments},
            provider="claude",
            role="user",
        )

        prompt = await runtime._build_contextual_prompt(
            session["id"],
            "",
            provider="claude",
            has_live_context=False,
            latest_attachments=attachments,
        )
        replay = await runtime.replay_session(session["id"])
        hydrated = await runtime.get_session(session["id"])

        attachment = hydrated["timeline"][0]["attachments"][0]
        assert Path(attachment["path"]).is_file()
        assert Path(attachment["path"]).read_text(encoding="utf-8") == "hello from attachment\n"
        assert hydrated["messages"][0]["attachments"][0]["name"] == "context.txt"
        assert replay["timeline"][0]["attachments"][0]["name"] == "context.txt"
        assert "Attached context:" in prompt
        assert "context.txt" in prompt
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_bridge_review_apply_patch_handler_updates_repo_and_emits_notice(tmp_path: Path):
    project_dir = _create_git_repo(tmp_path)
    target_file = project_dir / "app.txt"
    target_file.write_text("line one\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=project_dir, capture_output=True, check=True)

    patch = "\n".join(
        [
            "diff --git a/app.txt b/app.txt",
            "--- a/app.txt",
            "+++ b/app.txt",
            "@@ -1 +1,2 @@",
            " line one",
            "+line two",
        ]
    )

    runtime = DesktopRuntime()
    await runtime.initialize()
    previous_runtime = bridge.runtime
    bridge.runtime = runtime
    try:
        await runtime.open_project(str(project_dir))
        session = await runtime.create_session(str(project_dir), "critic", "claude", "Apply review patch")

        result = await bridge._handlers["review.apply_patch"](
            {
                "session_id": session["id"],
                "patch": patch,
            }
        )
        hydrated = await runtime.get_session(session["id"])

        assert result["status"] == "ok"
        assert target_file.read_text(encoding="utf-8") == "line one\nline two\n"
        assert any(
            item["kind"] == "system_notice" and item.get("title") == "Review patch applied"
            for item in hydrated["timeline"]
        )
    finally:
        bridge.runtime = previous_runtime
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_bridge_review_abandon_handler_emits_notice(tmp_path: Path):
    project_dir = _create_git_repo(tmp_path)

    runtime = DesktopRuntime()
    await runtime.initialize()
    previous_runtime = bridge.runtime
    bridge.runtime = runtime
    try:
        await runtime.open_project(str(project_dir))
        session = await runtime.create_session(str(project_dir), "critic", "claude", "Abandon review patch")

        result = await bridge._handlers["review.abandon"]({"session_id": session["id"]})
        hydrated = await runtime.get_session(session["id"])

        assert result["status"] == "ok"
        assert any(
            item["kind"] == "system_notice" and item.get("title") == "Review dismissed"
            for item in hydrated["timeline"]
        )
    finally:
        bridge.runtime = previous_runtime
        await runtime.shutdown()
