"""Triad Proxy — translates OpenAI API requests to provider CLI calls."""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from triad.core.accounts.manager import AccountManager
from triad.core.config import TriadConfig, load_config
from triad.core.providers import get_adapter
from triad.proxy.translator import translate_to_provider_prompt, format_response_event

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
_active_orchestrator: str = "claude"


def get_config() -> TriadConfig:
    global _config
    if _config is None:
        _config = load_config(Path.home() / ".triad" / "config.yaml")
    return _config


def get_account_manager() -> AccountManager:
    global _account_manager
    if _account_manager is None:
        config = get_config()
        _account_manager = AccountManager(profiles_dir=config.profiles_dir)
        _account_manager.discover()
    return _account_manager


@app.get("/health")
async def health():
    return {"status": "ok", "orchestrator": _active_orchestrator}


@app.get("/api/orchestrator")
async def get_orchestrator():
    return {"active": _active_orchestrator}


@app.post("/api/orchestrator")
async def set_orchestrator(request: Request):
    global _active_orchestrator
    body = await request.json()
    provider = body.get("provider", "claude")
    if provider not in ("claude", "codex", "gemini"):
        return {"error": f"Unknown provider: {provider}"}, 400
    _active_orchestrator = provider
    return {"active": _active_orchestrator}


@app.post("/api/telemetry/noop")
async def telemetry_noop():
    """Silently accept and discard telemetry from patched Codex app."""
    return {"status": "ok"}


@app.post("/api/responses")
async def create_response(request: Request):
    """Main endpoint — accepts OpenAI Responses API format, routes to active provider."""
    body = await request.json()

    # Extract prompt from OpenAI format
    prompt = translate_to_provider_prompt(body)
    model_requested = body.get("model", "")
    stream = body.get("stream", True)

    # Get provider and profile
    provider = _active_orchestrator
    mgr = get_account_manager()
    profile = mgr.get_next(provider)

    if profile is None:
        return {"error": f"No available {provider} profiles"}, 503

    adapter = get_adapter(provider)
    workdir = Path(body.get("cwd", str(Path.cwd())))

    if stream:
        return StreamingResponse(
            _stream_response(adapter, profile, prompt, workdir, body),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Non-streaming
        result = await adapter.execute(profile=profile, prompt=prompt, workdir=workdir)
        response_id = f"resp_{uuid.uuid4().hex[:16]}"
        return {
            "id": response_id,
            "object": "response",
            "status": "completed" if result.success else "failed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": result.stdout}],
                }
            ],
        }


async def _stream_response(adapter, profile, prompt, workdir, original_body):
    """Stream SSE events in OpenAI Responses API format."""
    response_id = f"resp_{uuid.uuid4().hex[:16]}"
    item_id = f"msg_{uuid.uuid4().hex[:12]}"

    # response.created
    yield f"data: {json.dumps({'type': 'response.created', 'response': {'id': response_id, 'status': 'in_progress', 'output': []}})}\n\n"

    # output_item.added
    yield f"data: {json.dumps({'type': 'response.output_item.added', 'output_index': 0, 'item': {'type': 'message', 'id': item_id, 'role': 'assistant', 'content': []}})}\n\n"

    # content_part.added
    yield f"data: {json.dumps({'type': 'response.content_part.added', 'output_index': 0, 'content_index': 0, 'part': {'type': 'output_text', 'text': ''}})}\n\n"

    # Stream provider output
    full_text = ""
    try:
        async for event in adapter.execute_stream(
            profile=profile,
            prompt=prompt,
            workdir=workdir,
        ):
            if event.kind == "text":
                full_text += event.text + "\n"
                delta_event = {
                    "type": "response.output_text.delta",
                    "output_index": 0,
                    "content_index": 0,
                    "delta": event.text + "\n",
                }
                yield f"data: {json.dumps(delta_event)}\n\n"

            elif event.kind == "error":
                error_event = {
                    "type": "response.output_text.delta",
                    "output_index": 0,
                    "content_index": 0,
                    "delta": f"\n[Error: {event.text}]\n",
                }
                yield f"data: {json.dumps(error_event)}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'response.output_text.delta', 'output_index': 0, 'content_index': 0, 'delta': f'[Proxy error: {e}]'})}\n\n"

    # content_part.done
    yield f"data: {json.dumps({'type': 'response.content_part.done', 'output_index': 0, 'content_index': 0, 'part': {'type': 'output_text', 'text': full_text}})}\n\n"

    # output_item.done
    yield f"data: {json.dumps({'type': 'response.output_item.done', 'output_index': 0, 'item': {'type': 'message', 'id': item_id, 'role': 'assistant', 'content': [{'type': 'output_text', 'text': full_text}]}})}\n\n"

    # response.completed
    yield f"data: {json.dumps({'type': 'response.completed', 'response': {'id': response_id, 'status': 'completed', 'output': [{'type': 'message', 'id': item_id, 'role': 'assistant', 'content': [{'type': 'output_text', 'text': full_text}]}]}})}\n\n"

    # Update account manager
    mgr = get_account_manager()
    mgr.mark_success(adapter.provider, profile.name)


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all(path: str, request: Request):
    """Catch-all for unknown API routes — log and return empty success."""
    body = None
    try:
        body = await request.json()
    except Exception:
        pass
    print(f"[proxy] unhandled: {request.method} /api/{path}")
    return {"status": "ok", "unhandled": True}
