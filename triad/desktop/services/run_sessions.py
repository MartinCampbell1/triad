from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any

from triad.core.providers import get_adapter
from triad.core.providers.base import is_rate_limited

from ..event_merger import EventMerger
from ..file_watcher import ClaudeSessionWatcher
from ..hooks_listener import HooksListener
from ..orchestrator import Orchestrator
from ..services.attachments import materialize_attachments
from ..services.attachments import summarize_attachment_names
from ..services.provider_streams import ProviderStreamRelay
from ..services.session_transfer import derive_title


async def get_orchestrator(runtime: Any) -> Orchestrator:
    if runtime._orchestrator is None:
        runtime._orchestrator = Orchestrator(
            on_event=runtime.emit_ui_event,
            account_manager=runtime.account_manager,
        )
    return runtime._orchestrator


async def ensure_event_pipeline(runtime: Any) -> None:
    if runtime._event_merger is not None:
        return

    async def forward_to_ui(event: dict[str, Any]) -> None:
        await runtime.emit_ui_event(event)

    runtime._event_merger = EventMerger(on_ui_event=forward_to_ui)
    runtime._hook_listener = HooksListener(on_event=runtime._event_merger.handle)
    await runtime._hook_listener.start()
    runtime._file_watcher = ClaudeSessionWatcher(on_event=runtime._event_merger.handle)
    await runtime._file_watcher.start()


async def handle_stream_event(runtime: Any, session_id: str, event: dict[str, Any]) -> None:
    normalized = dict(event)
    normalized.setdefault("session_id", session_id)
    if runtime._event_merger is None:
        await ensure_event_pipeline(runtime)
    assert runtime._event_merger is not None
    await runtime._event_merger.handle(normalized)


async def persist_ui_event(runtime: Any, event: dict[str, Any]) -> None:
    session_id = str(event.get("session_id", "")).strip()
    if not session_id:
        return
    ledger = await runtime.ledger()
    event_type = str(event.get("type", "system"))
    provider = event.get("provider")
    role = event.get("role")
    runtime_state = runtime._sessions.get(session_id)
    await ledger.append_event(
        session_id,
        event_type,
        event,
        provider=str(provider) if provider else None,
        role=str(role) if role else None,
        run_id=str(event.get("run_id")) if event.get("run_id") else None,
        agent=str(provider) if provider else None,
        content=str(event.get("content") or event.get("delta") or ""),
    )
    if runtime_state is not None and provider:
        runtime_state.provider = str(provider)
    if runtime_state is not None and event_type == "text_delta":
        runtime_state.state = "running"
    if event_type in {"message_finalized", "tool_use", "tool_result", "review_finding", "diff_snapshot", "system"}:
        await ledger.update_session_status(session_id, "running")
        if runtime_state is not None:
            runtime_state.state = "running"
    elif event_type == "run_completed":
        await ledger.update_session_status(session_id, "completed")
        if runtime_state is not None:
            runtime_state.state = "completed"
    elif event_type == "run_failed":
        await ledger.update_session_status(session_id, "failed")
        if runtime_state is not None:
            runtime_state.state = "failed"


async def run_headless(
    runtime: Any,
    *,
    session_id: str,
    prompt: str,
    provider: str,
    model: str | None,
    workdir: Path,
) -> None:
    adapter = get_adapter(provider)
    profile = runtime.account_manager.get_next(provider)
    if profile is None:
        await runtime.emit_ui_event(
            {
                "session_id": session_id,
                "type": "run_failed",
                "provider": provider,
                "error": f"No available {provider} accounts",
            }
        )
        return

    relay = ProviderStreamRelay(
        session_id=session_id,
        provider=provider,
        on_event=runtime.emit_ui_event,
        stream_text=True,
    )
    try:
        outcome = await relay.consume(
            adapter.execute_stream(
                profile=profile,
                prompt=prompt,
                workdir=workdir,
                model=model,
            )
        )
        if outcome.error_text or outcome.returncode not in (None, 0):
            error_text = outcome.error_text or f"{provider} exited with code {outcome.returncode}"
            if is_rate_limited(error_text):
                runtime.account_manager.mark_rate_limited(provider, profile.name)
            await runtime.emit_ui_event(
                {
                    "session_id": session_id,
                    "type": "run_failed",
                    "provider": provider,
                    "error": error_text,
                }
            )
            return

        runtime.account_manager.mark_success(provider, profile.name)
        final_text = outcome.output
        if final_text:
            await runtime.emit_ui_event(
                {
                    "session_id": session_id,
                    "type": "message_finalized",
                    "provider": provider,
                    "content": final_text,
                }
            )
        await runtime.emit_ui_event(
            {
                "session_id": session_id,
                "type": "run_completed",
                "provider": provider,
            }
        )
    except asyncio.CancelledError:
        await runtime.emit_ui_event(
            {
                "session_id": session_id,
                "type": "run_failed",
                "provider": provider,
                "error": "Run cancelled",
            }
        )
    except Exception as exc:
        await runtime.emit_ui_event(
            {
                "session_id": session_id,
                "type": "run_failed",
                "provider": provider,
                "error": str(exc),
            }
        )


async def prepare_mode_session(
    runtime: Any,
    *,
    session_id: str,
    prompt: str,
    project_path: str | None = None,
    mode: str,
    provider: str,
    attachments: Any = None,
) -> tuple[Any, str]:
    ledger = await runtime.ledger()
    session_runtime = runtime._sessions.get(session_id)
    if session_runtime is None:
        session_runtime = await runtime._hydrate_session(session_id, project_path=project_path)
        runtime._sessions[session_id] = session_runtime
    if session_runtime.pty is not None:
        with contextlib.suppress(Exception):
            await session_runtime.pty.stop()
        session_runtime.pty = None
    await runtime._detach_terminal_host(session_runtime)
    session_runtime.transcript_capture = "typed"
    if runtime._file_watcher is not None:
        runtime._file_watcher.unwatch_session(session_id)
    session_runtime.provider = provider
    session_runtime.mode = mode
    session_runtime.state = "running"
    resolved_attachments = materialize_attachments(
        attachments,
        project_path=session_runtime.project_path,
        artifacts_dir=runtime.config.artifacts_dir,
        session_id=session_id,
    )

    await ledger.append_event(
        session_id,
        "user.message",
        {"content": prompt, "attachments": resolved_attachments},
        provider=provider,
        role="user",
        content=prompt,
    )

    existing = await ledger.get_session(session_id)
    existing_title = (existing or {}).get("title")
    if not existing_title:
        new_title = derive_title(prompt) if prompt.strip() else derive_title(summarize_attachment_names(resolved_attachments))
        await ledger.update_session_title(session_id, new_title)
        session_runtime.title = new_title

    await ledger.update_session_status(session_id, "running")
    effective_prompt = await runtime._build_contextual_prompt(
        session_id,
        prompt,
        provider=provider,
        has_live_context=False,
        latest_attachments=resolved_attachments,
    )
    return session_runtime, effective_prompt


async def start_critic_session(
    runtime: Any,
    *,
    session_id: str,
    prompt: str,
    project_path: str | None = None,
    writer_provider: str | None = None,
    critic_provider: str | None = None,
    max_rounds: int = 3,
    model: str | None = None,
    attachments: Any = None,
) -> dict[str, Any]:
    selected_writer = (writer_provider or "claude").strip() or "claude"
    session_runtime, effective_prompt = await prepare_mode_session(
        runtime,
        session_id=session_id,
        prompt=prompt,
        project_path=project_path,
        mode="critic",
        provider=selected_writer,
        attachments=attachments,
    )
    selected_critic = (critic_provider or default_critic_provider(runtime, selected_writer)).strip()

    async def run() -> None:
        orchestrator = await get_orchestrator(runtime)
        await orchestrator.run_critic(
            session_id=session_id,
            prompt=effective_prompt,
            workdir=Path(session_runtime.project_path),
            writer_provider=selected_writer,
            critic_provider=selected_critic,
            max_rounds=max_rounds,
            writer_model=model,
        )

    task = asyncio.create_task(run())
    runtime._background_tasks.add(task)
    runtime._session_tasks.setdefault(session_id, set()).add(task)
    task.add_done_callback(lambda completed: runtime._discard_task(session_id, completed))
    return {
        "status": "started",
        "session_id": session_id,
        "writer_provider": selected_writer,
        "critic_provider": selected_critic,
    }


async def start_brainstorm_session(
    runtime: Any,
    *,
    session_id: str,
    prompt: str,
    project_path: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    attachments: Any = None,
) -> dict[str, Any]:
    primary_provider = (provider or "claude").strip() or "claude"
    session_runtime, effective_prompt = await prepare_mode_session(
        runtime,
        session_id=session_id,
        prompt=prompt,
        project_path=project_path,
        mode="brainstorm",
        provider=primary_provider,
        attachments=attachments,
    )
    orchestrator = await get_orchestrator(runtime)
    ideators, moderator = orchestrator.default_brainstorm_providers(primary_provider)

    async def run() -> None:
        await orchestrator.run_brainstorm(
            session_id=session_id,
            prompt=effective_prompt,
            workdir=Path(session_runtime.project_path),
            ideator_providers=ideators,
            moderator_provider=moderator,
            ideator_model=model,
            moderator_model=model if moderator == primary_provider else None,
        )

    task = asyncio.create_task(run())
    runtime._background_tasks.add(task)
    runtime._session_tasks.setdefault(session_id, set()).add(task)
    task.add_done_callback(lambda completed: runtime._discard_task(session_id, completed))
    return {
        "status": "started",
        "session_id": session_id,
        "ideator_providers": ideators,
        "moderator_provider": moderator,
    }


async def start_delegate_session(
    runtime: Any,
    *,
    session_id: str,
    prompt: str,
    project_path: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    attachments: Any = None,
) -> dict[str, Any]:
    primary_provider = (provider or "claude").strip() or "claude"
    session_runtime, effective_prompt = await prepare_mode_session(
        runtime,
        session_id=session_id,
        prompt=prompt,
        project_path=project_path,
        mode="delegate",
        provider=primary_provider,
        attachments=attachments,
    )
    orchestrator = await get_orchestrator(runtime)
    providers = orchestrator.default_delegate_providers(primary_provider)

    async def run() -> None:
        await orchestrator.run_delegate(
            session_id=session_id,
            prompt=effective_prompt,
            workdir=Path(session_runtime.project_path),
            lane_providers=providers,
            model=model,
        )

    task = asyncio.create_task(run())
    runtime._background_tasks.add(task)
    runtime._session_tasks.setdefault(session_id, set()).add(task)
    task.add_done_callback(lambda completed: runtime._discard_task(session_id, completed))
    return {
        "status": "started",
        "session_id": session_id,
        "providers": providers,
    }


def default_critic_provider(runtime: Any, writer_provider: str) -> str:
    candidates = [provider for provider in ("codex", "claude", "gemini") if provider != writer_provider]
    for provider in candidates:
        if runtime.account_manager.pools.get(provider):
            return provider
    return candidates[0] if candidates else writer_provider
