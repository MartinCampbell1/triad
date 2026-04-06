"""Triad Proxy — translates OpenAI API requests to provider CLI calls."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from triad.core.account_diagnostics import build_account_diagnostics_snapshot
from triad.core.accounts.manager import AccountManager
from triad.core.config import TriadConfig, get_default_config_path, load_config
from triad.core.provider_sessions import (
    import_current_session,
    is_valid_provider,
    open_login_terminal,
)
from triad.core.providers import get_adapter
from triad.core.providers.base import is_rate_limited
from triad.proxy.runtime_state import ThreadRuntimeStore
from triad.proxy.translator import format_response_event, translate_request

app = FastAPI(title="Triad Proxy", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
_config: TriadConfig | None = None
_account_manager: AccountManager | None = None
_thread_store: ThreadRuntimeStore | None = None
_active_orchestrator: str = "codex"


def get_config() -> TriadConfig:
    global _config
    if _config is None:
        _config = load_config(get_default_config_path())
    return _config


def get_account_manager() -> AccountManager:
    global _account_manager
    if _account_manager is None:
        config = get_config()
        _account_manager = AccountManager(
            profiles_dir=config.profiles_dir,
            cooldown_base=config.cooldown_base_sec,
        )
        _account_manager.discover()
    return _account_manager


def reload_account_manager() -> AccountManager:
    global _account_manager
    _account_manager = None
    return get_account_manager()


def get_thread_store() -> ThreadRuntimeStore:
    global _thread_store
    if _thread_store is None:
        _thread_store = ThreadRuntimeStore(
            storage_dir=get_config().triad_home / "runtime" / "threads"
        )
    return _thread_store


def provider_priority() -> list[str]:
    config = get_config()
    ordered: list[str] = []
    for provider in [*config.providers_priority, "codex", "claude", "gemini"]:
        if provider not in ("codex", "claude", "gemini"):
            continue
        if provider not in ordered:
            ordered.append(provider)
    return ordered


def resolve_provider_order(*, requested_provider: str | None = None) -> list[str]:
    preferred = (requested_provider or _active_orchestrator or "").strip() or provider_priority()[0]
    ordered: list[str] = []
    for provider in [preferred, *provider_priority()]:
        if provider not in ("codex", "claude", "gemini"):
            continue
        if provider not in ordered:
            ordered.append(provider)
    return ordered


def select_provider_profile(
    manager: AccountManager,
    provider_order: list[str],
    *,
    tried_profiles: set[tuple[str, str]] | None = None,
) -> tuple[str | None, object | None]:
    for _ in range(max(1, len(provider_order) * 8)):
        for provider in provider_order:
            profile = manager.get_next(provider)
            if profile is None:
                continue
            profile_name = str(getattr(profile, "name", "") or "")
            key = (provider, profile_name)
            if tried_profiles is not None and key in tried_profiles:
                continue
            if tried_profiles is not None:
                tried_profiles.add(key)
            return provider, profile
        break
    return None, None


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "orchestrator": _active_orchestrator,
        "providers_priority": provider_priority(),
    }


@app.get("/api/accounts")
async def list_accounts():
    manager = get_account_manager()
    return {
        "accounts": {
            provider: manager.pool_status(provider)
            for provider in provider_priority()
        }
    }


@app.get("/api/accounts/health")
async def accounts_health():
    manager = get_account_manager()
    pools = [manager.pool_status(provider) for provider in provider_priority()]
    total = sum(len(pool) for pool in pools)
    available = sum(sum(1 for item in pool if item["available"]) for pool in pools)
    return {
        "total": total,
        "available": available,
        "on_cooldown": total - available,
    }


@app.get("/api/accounts/diagnostics")
async def account_diagnostics():
    config = get_config()
    manager = get_account_manager()
    return build_account_diagnostics_snapshot(config, manager)


@app.post("/api/accounts/diagnostics/refresh")
async def refresh_account_diagnostics():
    config = get_config()
    manager = reload_account_manager()
    return build_account_diagnostics_snapshot(config, manager)


@app.post("/api/accounts/reload")
async def reload_accounts():
    manager = reload_account_manager()
    return {
        "status": "ok",
        "providers": {
            provider: manager.pool_status(provider)
            for provider in provider_priority()
        },
    }


@app.post("/api/accounts/{provider}/open-login")
async def open_provider_login(provider: str):
    if not is_valid_provider(provider):
        raise HTTPException(404, f"Unknown provider: {provider}")
    command = open_login_terminal(provider)
    return {
        "status": "ok",
        "provider": provider,
        "command": command,
        "message": "Login flow opened in a separate terminal window.",
    }


@app.post("/api/accounts/{provider}/import")
async def import_provider_session(provider: str):
    if not is_valid_provider(provider):
        raise HTTPException(404, f"Unknown provider: {provider}")

    config = get_config()
    account_name = import_current_session(provider, config.profiles_dir)
    reload_account_manager()
    return {
        "status": "ok",
        "provider": provider,
        "account_name": account_name,
        "message": f"Imported {provider} session as {account_name}.",
    }


@app.get("/api/orchestrator")
async def get_orchestrator():
    return {"active": _active_orchestrator}


@app.post("/api/orchestrator")
async def set_orchestrator(request: Request):
    global _active_orchestrator
    body = await request.json()
    provider = body.get("provider", "claude")
    if provider not in ("claude", "codex", "gemini"):
        raise HTTPException(
            status_code=400,
            detail={"error": f"Unknown provider: {provider}"},
        )
    _active_orchestrator = provider
    return {"active": _active_orchestrator}


@app.get("/api/models")
async def list_models():
    """Return the model catalog consumed by the native dropdown."""
    return {"data": TRIAD_MODELS}


@app.post("/api/telemetry/noop")
async def telemetry_noop():
    """Silently accept and discard telemetry from patched Codex app."""
    return {"status": "ok"}


# --- Model list for native dropdown ---

TRIAD_MODELS = [
    {
        "model": "claude-opus-4-6",
        "hidden": False,
        "isDefault": True,
        "displayName": "Claude Opus 4.6",
        "provider": "claude",
        "supportedReasoningEfforts": [
            {"reasoningEffort": "low", "description": "Quick"},
            {"reasoningEffort": "medium", "description": "Balanced"},
            {"reasoningEffort": "high", "description": "Thorough"},
            {"reasoningEffort": "xhigh", "description": "Maximum"},
        ],
    },
    {
        "model": "claude-sonnet-4-6",
        "hidden": False,
        "isDefault": False,
        "displayName": "Claude Sonnet 4.6",
        "provider": "claude",
        "supportedReasoningEfforts": [
            {"reasoningEffort": "low", "description": "Quick"},
            {"reasoningEffort": "medium", "description": "Balanced"},
            {"reasoningEffort": "high", "description": "Thorough"},
        ],
    },
    {
        "model": "claude-haiku-4-5",
        "hidden": False,
        "isDefault": False,
        "displayName": "Claude Haiku 4.5",
        "provider": "claude",
        "supportedReasoningEfforts": [
            {"reasoningEffort": "low", "description": "Quick"},
            {"reasoningEffort": "medium", "description": "Balanced"},
        ],
    },
    {
        "model": "codex-mini-latest",
        "hidden": False,
        "isDefault": False,
        "displayName": "Codex Mini",
        "provider": "codex",
        "supportedReasoningEfforts": [
            {"reasoningEffort": "medium", "description": "Balanced"},
            {"reasoningEffort": "high", "description": "Thorough"},
        ],
    },
    {
        "model": "gpt-5.4",
        "hidden": False,
        "isDefault": False,
        "displayName": "GPT-5.4",
        "provider": "codex",
        "supportedReasoningEfforts": [
            {"reasoningEffort": "low", "description": "Quick"},
            {"reasoningEffort": "medium", "description": "Balanced"},
            {"reasoningEffort": "high", "description": "Thorough"},
            {"reasoningEffort": "xhigh", "description": "Maximum"},
        ],
    },
    {
        "model": "gpt-5.3-codex",
        "hidden": False,
        "isDefault": False,
        "displayName": "GPT-5.3 Codex",
        "provider": "codex",
        "supportedReasoningEfforts": [
            {"reasoningEffort": "medium", "description": "Balanced"},
            {"reasoningEffort": "high", "description": "Thorough"},
        ],
    },
    {
        "model": "gemini-2.5-pro",
        "hidden": False,
        "isDefault": False,
        "displayName": "Gemini 2.5 Pro",
        "provider": "gemini",
        "supportedReasoningEfforts": [
            {"reasoningEffort": "medium", "description": "Balanced"},
            {"reasoningEffort": "high", "description": "Thorough"},
        ],
    },
    {
        "model": "gemini-2.5-flash",
        "hidden": False,
        "isDefault": False,
        "displayName": "Gemini 2.5 Flash",
        "provider": "gemini",
        "supportedReasoningEfforts": [
            {"reasoningEffort": "low", "description": "Quick"},
            {"reasoningEffort": "medium", "description": "Balanced"},
        ],
    },
]

MODEL_TO_PROVIDER: dict[str, str] = {m["model"]: m["provider"] for m in TRIAD_MODELS}


def resolve_provider(model: str) -> str:
    """Map a model name to its provider. Falls back to active orchestrator."""
    if model in MODEL_TO_PROVIDER:
        return MODEL_TO_PROVIDER[model]
    if model.startswith("claude"):
        return "claude"
    if model.startswith("gemini"):
        return "gemini"
    return "codex"  # gpt-*, codex-*, and anything else → codex


@app.post("/api/responses")
async def create_response(request: Request):
    """Main endpoint — accepts OpenAI Responses API format, routes to active provider."""
    body = await request.json()
    translated = translate_request(body)
    response_id = f"resp_{uuid.uuid4().hex[:16]}"

    # Extract prompt from OpenAI format
    model_requested = body.get("model", "")
    stream = body.get("stream", True)

    # Map model to provider (model selection overrides orchestrator)
    requested_provider = resolve_provider(model_requested) if model_requested else None
    provider_order = resolve_provider_order(requested_provider=requested_provider)
    mgr = get_account_manager()
    tried_profiles: set[tuple[str, str]] = set()
    workdir = Path(body.get("cwd", str(Path.cwd())))
    provider, profile = select_provider_profile(
        mgr,
        provider_order,
        tried_profiles=tried_profiles,
    )

    if profile is None or provider is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "No available provider profiles",
                "providers_tried": provider_order,
            },
        )

    thread_store = get_thread_store()
    thread_key = thread_store.resolve_thread_key(
        explicit_thread_key=translated.explicit_thread_key,
        previous_response_id=translated.previous_response_id,
        fallback_response_id=response_id,
    )
    thread_store.record_request_context(
        thread_key,
        cwd=str(workdir),
        metadata=body.get("metadata"),
        turns=translated.turns,
    )
    prompt = thread_store.build_prompt(
        thread_key,
        provider=provider,
        current_user_turn=translated.current_user_turn,
        fallback_prompt=translated.prompt,
        cwd=str(workdir),
    )
    thread_store.record_user_turn(thread_key, translated.current_user_turn)
    thread_store.register_response(thread_key, response_id)

    if stream:
        return StreamingResponse(
            _stream_response(
                prompt,
                workdir,
                body,
                response_id=response_id,
                thread_store=thread_store,
                thread_key=thread_key,
                provider_order=provider_order,
                provider=provider,
                profile=profile,
                tried_profiles=tried_profiles,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Non-streaming
        last_result = None
        last_provider = provider
        while provider is not None and profile is not None:
            adapter = get_adapter(provider)
            result = await adapter.execute(profile=profile, prompt=prompt, workdir=workdir)
            last_result = result
            last_provider = provider
            if result.rate_limited:
                mgr.mark_rate_limited(provider, profile.name)
                provider, profile = select_provider_profile(
                    mgr,
                    provider_order,
                    tried_profiles=tried_profiles,
                )
                continue
            if result.success:
                mgr.mark_success(provider, profile.name)
                thread_store.mark_provider(thread_key, provider, profile.name)
                thread_store.record_assistant_turn(thread_key, result.stdout)
                return {
                    "id": response_id,
                    "object": "response",
                    "status": "completed",
                    "provider": provider,
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": result.stdout}],
                        }
                    ],
                }
            return {
                "id": response_id,
                "object": "response",
                "status": "failed",
                "provider": provider,
                "error": {"message": result.stderr or "Provider execution failed"},
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": result.stdout}],
                    }
                ],
            }

        failed_result = getattr(last_result, "stdout", "") if last_result is not None else ""
        failed_reason = (
            getattr(last_result, "stderr", "")
            if last_result is not None and getattr(last_result, "stderr", "")
            else "No available provider profiles after retries"
        )
        return {
            "id": response_id,
            "object": "response",
            "status": "failed",
            "provider": last_provider,
            "error": {"message": failed_reason},
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": failed_result}],
                }
            ],
        }


async def _stream_response(
    prompt,
    workdir,
    _original_body,
    *,
    response_id: str,
    thread_store: ThreadRuntimeStore,
    thread_key: str,
    provider_order: list[str],
    provider: str,
    profile,
    tried_profiles: set[tuple[str, str]],
):
    """Stream SSE events in OpenAI Responses API format."""
    item_id = f"msg_{uuid.uuid4().hex[:12]}"

    sequence_number = 0

    def emit(event_type: str, **payload) -> str:
        nonlocal sequence_number
        payload["sequence_number"] = sequence_number
        sequence_number += 1
        return format_response_event(event_type, payload)

    # response.created
    yield emit(
        "response.created",
        response={
            "id": response_id,
            "status": "in_progress",
            "output": [],
        },
    )

    # response.in_progress
    yield emit(
        "response.in_progress",
        response={
            "id": response_id,
            "status": "in_progress",
            "output": [],
        },
    )

    # output_item.added
    yield emit(
        "response.output_item.added",
        output_index=0,
        item={
            "type": "message",
            "id": item_id,
            "status": "in_progress",
            "role": "assistant",
            "content": [],
        },
    )

    # content_part.added
    yield emit(
        "response.content_part.added",
        output_index=0,
        content_index=0,
        item_id=item_id,
        part={
            "type": "output_text",
            "text": "",
        },
    )

    # Stream provider output
    mgr = get_account_manager()
    current_provider = provider
    current_profile = profile
    full_text = ""
    failure_reason = None
    last_provider = provider
    while current_provider is not None and current_profile is not None:
        adapter = get_adapter(current_provider)
        last_provider = current_provider
        stream_failed = False
        failure_reason = None
        attempt_text = ""
        try:
            async for event in adapter.execute_stream(
                profile=current_profile,
                prompt=prompt,
                workdir=workdir,
            ):
                if event.kind == "text":
                    attempt_text += event.text + "\n"
                    full_text += event.text + "\n"
                    yield emit(
                        "response.output_text.delta",
                        item_id=item_id,
                        output_index=0,
                        content_index=0,
                        delta=event.text + "\n",
                    )

                elif event.kind == "error":
                    stream_failed = True
                    failure_reason = event.text or "Provider stream failed"
                    break

        except Exception as e:
            stream_failed = True
            failure_reason = str(e)

        if not stream_failed:
            mgr.mark_success(adapter.provider, current_profile.name)
            thread_store.mark_provider(thread_key, adapter.provider, current_profile.name)
            thread_store.record_assistant_turn(thread_key, full_text)
            break

        if failure_reason and is_rate_limited(failure_reason):
            mgr.mark_rate_limited(adapter.provider, current_profile.name)
            if not attempt_text.strip():
                current_provider, current_profile = select_provider_profile(
                    mgr,
                    provider_order,
                    tried_profiles=tried_profiles,
                )
                if current_provider is not None and current_profile is not None:
                    continue

        if failure_reason:
            yield emit(
                "response.output_text.delta",
                item_id=item_id,
                output_index=0,
                content_index=0,
                delta=f"\n[Error: {failure_reason}]\n",
            )
        yield emit(
            "response.failed",
            response={
                "id": response_id,
                "status": "failed",
                "output": [
                    {
                        "type": "message",
                        "id": item_id,
                        "status": "failed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": full_text,
                            }
                        ],
                    }
                ],
                "error": {
                    "message": failure_reason or "Provider stream failed",
                },
            },
        )
        return
    else:
        yield emit(
            "response.failed",
            response={
                "id": response_id,
                "status": "failed",
                "output": [
                    {
                        "type": "message",
                        "id": item_id,
                        "status": "failed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": full_text,
                            }
                        ],
                    }
                ],
                "error": {
                    "message": failure_reason or "No available provider profiles after retries",
                },
            },
        )
        return

    # content_part.done
    yield emit(
        "response.output_text.done",
        item_id=item_id,
        output_index=0,
        content_index=0,
        text=full_text,
    )

    yield emit(
        "response.content_part.done",
        output_index=0,
        content_index=0,
        item_id=item_id,
        part={
            "type": "output_text",
            "text": full_text,
        },
    )

    # output_item.done
    yield emit(
        "response.output_item.done",
        output_index=0,
        item={
            "type": "message",
            "id": item_id,
            "status": "completed",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": full_text,
                }
            ],
        },
    )

    # response.completed
    yield emit(
        "response.completed",
        response={
            "id": response_id,
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "id": item_id,
                    "status": "completed",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": full_text,
                        }
                    ],
                }
            ],
        },
    )

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all(path: str, request: Request):
    """Catch-all for unknown API routes — log and return a 404."""
    body = None
    try:
        body = await request.json()
    except Exception:
        pass
    print(f"[proxy] unhandled: {request.method} /api/{path}", body if body is not None else "")
    raise HTTPException(
        status_code=404,
        detail={
            "error": "Unhandled proxy route",
            "method": request.method,
            "path": f"/api/{path}",
        },
    )
