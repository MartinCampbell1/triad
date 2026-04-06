"""Translate between OpenAI API format and provider prompts."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptTurn:
    role: str
    text: str


@dataclass
class TranslatedRequest:
    prompt: str
    current_user_turn: str
    turns: list[PromptTurn] = field(default_factory=list)
    previous_response_id: str | None = None
    explicit_thread_key: str | None = None


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    parts.append(text)
            elif isinstance(item, dict):
                item_type = item.get("type")
                if item_type in {"input_text", "output_text", "text"}:
                    text = str(item.get("text", "")).strip()
                    if text:
                        parts.append(text)
        return "\n".join(parts).strip()
    return ""


def _turns_to_prompt(turns: list[PromptTurn]) -> str:
    parts: list[str] = []
    for turn in turns:
        role = turn.role.strip()
        if role:
            parts.append(f"[{role}]: {turn.text}")
        else:
            parts.append(turn.text)
    return "\n\n".join(parts)


def _extract_explicit_thread_key(body: dict) -> str | None:
    candidates = [
        body.get("thread_id"),
        body.get("conversation_id"),
        body.get("chat_id"),
        body.get("session_id"),
    ]
    metadata = body.get("metadata")
    if isinstance(metadata, dict):
        candidates.extend([
            metadata.get("thread_id"),
            metadata.get("conversation_id"),
            metadata.get("triad_thread_key"),
        ])
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value
    return None


def translate_request(body: dict) -> TranslatedRequest:
    turns: list[PromptTurn] = []
    direct_prompt: str | None = None

    input_field = body.get("input")
    if isinstance(input_field, str):
        text = input_field.strip()
        if text:
            direct_prompt = text
            turns.append(PromptTurn(role="user", text=text))
    elif isinstance(input_field, list):
        for item in input_field:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    turns.append(PromptTurn(role="user", text=text))
            elif isinstance(item, dict):
                role = str(item.get("role") or "user").strip() or "user"
                text = _content_to_text(item.get("content", ""))
                if text:
                    turns.append(PromptTurn(role=role, text=text))

    if not turns:
        messages = body.get("messages", [])
        if isinstance(messages, list):
            for message in messages:
                if not isinstance(message, dict):
                    continue
                role = str(message.get("role") or "").strip()
                text = _content_to_text(message.get("content", ""))
                if text:
                    turns.append(PromptTurn(role=role, text=text))

    prompt = direct_prompt if direct_prompt is not None else _turns_to_prompt(turns)
    if not prompt:
        prompt = str(body.get("prompt", "") or "")

    current_user_turn = ""
    for turn in reversed(turns):
        if turn.role in {"user", "input"}:
            current_user_turn = turn.text
            break
    if not current_user_turn and turns:
        current_user_turn = turns[-1].text
    if not current_user_turn:
        current_user_turn = prompt

    previous_response_id = str(body.get("previous_response_id") or "").strip() or None
    explicit_thread_key = _extract_explicit_thread_key(body)
    return TranslatedRequest(
        prompt=prompt,
        current_user_turn=current_user_turn,
        turns=turns,
        previous_response_id=previous_response_id,
        explicit_thread_key=explicit_thread_key,
    )


def translate_to_provider_prompt(body: dict) -> str:
    """Extract a plain-text prompt from an OpenAI Responses API request body."""
    return translate_request(body).prompt


def format_response_event(event_type: str, data: dict) -> str:
    """Format a single SSE event."""
    import json
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"
