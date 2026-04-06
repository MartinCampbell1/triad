from __future__ import annotations

from typing import Any

from .runtime_catalog import list_capabilities as list_runtime_capabilities
from .runtime_catalog import list_modes as list_runtime_modes
from .runtime_catalog import list_models as list_runtime_models


JsonValue = dict[str, Any]


def register_non_terminal_handlers(bridge: Any) -> None:
    @bridge.method("ping")
    async def ping(_: JsonValue) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "triad-desktop",
            "version": "0.1.0",
        }

    @bridge.method("project.open")
    async def project_open(params: JsonValue) -> dict[str, Any]:
        path = str(params.get("path", ""))
        return await bridge.runtime.open_project(path)

    @bridge.method("project.list")
    async def project_list(_: JsonValue) -> dict[str, Any]:
        return {"projects": await bridge.runtime.list_projects()}

    @bridge.method("app.get_state")
    async def app_get_state(_: JsonValue) -> dict[str, Any]:
        return await bridge.runtime.get_app_state()

    @bridge.method("session.create")
    async def session_create(params: JsonValue) -> dict[str, Any]:
        project_path = str(params.get("project_path", ""))
        mode = str(params.get("mode", "solo"))
        provider = str(params.get("provider", "claude"))
        title = params.get("title")
        return await bridge.runtime.create_session(
            project_path=project_path,
            mode=mode,
            provider=provider,
            title=str(title) if title else None,
        )

    @bridge.method("session.list")
    async def session_list(params: JsonValue) -> dict[str, Any]:
        project_path = params.get("project_path")
        return {
            "sessions": await bridge.runtime.list_sessions(
                project_path=str(project_path) if project_path else None
            )
        }

    @bridge.method("session.get")
    async def session_get(params: JsonValue) -> dict[str, Any]:
        session_id = str(params.get("session_id", ""))
        if not session_id:
            raise ValueError("session_id is required")
        return await bridge.runtime.get_session(session_id)

    @bridge.method("session.compare")
    async def session_compare(params: JsonValue) -> dict[str, Any]:
        left_session_id = str(params.get("left_session_id", ""))
        right_session_id = str(params.get("right_session_id", ""))
        if not left_session_id:
            raise ValueError("left_session_id is required")
        if not right_session_id:
            raise ValueError("right_session_id is required")
        return await bridge.runtime.compare_sessions(left_session_id, right_session_id)

    @bridge.method("session.replay")
    async def session_replay(params: JsonValue) -> dict[str, Any]:
        session_id = str(params.get("session_id", ""))
        if not session_id:
            raise ValueError("session_id is required")
        return await bridge.runtime.replay_session(session_id)

    @bridge.method("session.fork")
    async def session_fork(params: JsonValue) -> dict[str, Any]:
        session_id = str(params.get("session_id", ""))
        title = params.get("title")
        if not session_id:
            raise ValueError("session_id is required")
        return await bridge.runtime.fork_session(
            session_id,
            title=str(title) if title else None,
        )

    @bridge.method("session.export")
    async def session_export(params: JsonValue) -> dict[str, Any]:
        session_id = str(params.get("session_id", ""))
        format_name = str(params.get("format", "archive"))
        output_path = params.get("path")
        if not session_id:
            raise ValueError("session_id is required")
        return await bridge.runtime.export_session(
            session_id,
            format_name=format_name,
            output_path=str(output_path) if output_path else None,
        )

    @bridge.method("session.import")
    async def session_import(params: JsonValue) -> dict[str, Any]:
        input_path = str(params.get("path", ""))
        if not input_path:
            raise ValueError("path is required")
        return await bridge.runtime.import_session(input_path)

    @bridge.method("session.send")
    async def session_send(params: JsonValue) -> dict[str, Any]:
        session_id = str(params.get("session_id", ""))
        content = str(params.get("content", ""))
        project_path = params.get("project_path")
        provider = params.get("provider")
        model = params.get("model")
        attachments = params.get("attachments")
        if not session_id:
            raise ValueError("session_id is required")
        if not content.strip() and not attachments:
            raise ValueError("content or attachments are required")
        return await bridge.runtime.send_session_message(
            session_id=session_id,
            content=content,
            project_path=str(project_path) if project_path else None,
            provider=str(provider) if provider else None,
            model=str(model) if model else None,
            attachments=attachments,
        )

    @bridge.method("session.stop")
    async def session_stop(params: JsonValue) -> dict[str, Any]:
        session_id = str(params.get("session_id", ""))
        if not session_id:
            raise ValueError("session_id is required")
        return await bridge.runtime.stop_session(session_id)

    @bridge.method("critic.start")
    async def critic_start(params: JsonValue) -> dict[str, Any]:
        session_id = str(params.get("session_id", ""))
        prompt = str(params.get("prompt", ""))
        project_path = params.get("project_path")
        writer_provider = params.get("writer")
        critic_provider = params.get("critic")
        max_rounds = int(params.get("max_rounds") or 3)
        model = params.get("model")
        attachments = params.get("attachments")
        if not session_id:
            raise ValueError("session_id is required")
        if not prompt.strip() and not attachments:
            raise ValueError("prompt or attachments are required")
        return await bridge.runtime.start_critic_session(
            session_id=session_id,
            prompt=prompt,
            project_path=str(project_path) if project_path else None,
            writer_provider=str(writer_provider) if writer_provider else None,
            critic_provider=str(critic_provider) if critic_provider else None,
            max_rounds=max_rounds,
            model=str(model) if model else None,
            attachments=attachments,
        )

    @bridge.method("brainstorm.start")
    async def brainstorm_start(params: JsonValue) -> dict[str, Any]:
        session_id = str(params.get("session_id", ""))
        prompt = str(params.get("prompt", ""))
        project_path = params.get("project_path")
        provider = params.get("provider")
        model = params.get("model")
        attachments = params.get("attachments")
        if not session_id:
            raise ValueError("session_id is required")
        if not prompt.strip() and not attachments:
            raise ValueError("prompt or attachments are required")
        return await bridge.runtime.start_brainstorm_session(
            session_id=session_id,
            prompt=prompt,
            project_path=str(project_path) if project_path else None,
            provider=str(provider) if provider else None,
            model=str(model) if model else None,
            attachments=attachments,
        )

    @bridge.method("delegate.start")
    async def delegate_start(params: JsonValue) -> dict[str, Any]:
        session_id = str(params.get("session_id", ""))
        prompt = str(params.get("prompt", ""))
        project_path = params.get("project_path")
        provider = params.get("provider")
        model = params.get("model")
        attachments = params.get("attachments")
        if not session_id:
            raise ValueError("session_id is required")
        if not prompt.strip() and not attachments:
            raise ValueError("prompt or attachments are required")
        return await bridge.runtime.start_delegate_session(
            session_id=session_id,
            prompt=prompt,
            project_path=str(project_path) if project_path else None,
            provider=str(provider) if provider else None,
            model=str(model) if model else None,
            attachments=attachments,
        )

    @bridge.method("search")
    async def search(params: JsonValue) -> dict[str, Any]:
        query = str(params.get("query", ""))
        limit = int(params.get("limit") or 50)
        return {"results": await bridge.runtime.search(query, limit)}

    @bridge.method("diagnostics")
    async def diagnostics(_: JsonValue) -> dict[str, Any]:
        return await bridge.runtime.get_diagnostics()

    @bridge.method("review.apply_patch")
    async def review_apply_patch(params: JsonValue) -> dict[str, Any]:
        session_id = str(params.get("session_id", ""))
        patch = str(params.get("patch", ""))
        if not session_id:
            raise ValueError("session_id is required")
        if not patch.strip():
            raise ValueError("patch is required")
        return await bridge.runtime.apply_review_patch(session_id, patch)

    @bridge.method("review.abandon")
    async def review_abandon(params: JsonValue) -> dict[str, Any]:
        session_id = str(params.get("session_id", ""))
        if not session_id:
            raise ValueError("session_id is required")
        return await bridge.runtime.abandon_review(session_id)

    @bridge.method("capabilities.list")
    async def capabilities_list(params: JsonValue) -> dict[str, Any]:
        provider = str(params.get("provider")) if params.get("provider") else None
        mode = str(params.get("mode")) if params.get("mode") else None
        return await list_runtime_capabilities(bridge.runtime, provider, mode)

    @bridge.method("models.list")
    async def models_list(params: JsonValue) -> dict[str, Any]:
        provider = str(params.get("provider")) if params.get("provider") else None
        return {"models": await list_runtime_models(provider)}

    @bridge.method("modes.list")
    async def modes_list(_: JsonValue) -> dict[str, Any]:
        return {"modes": await list_runtime_modes()}
