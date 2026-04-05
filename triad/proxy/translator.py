"""Translate between OpenAI API format and provider prompts."""
from __future__ import annotations


def translate_to_provider_prompt(body: dict) -> str:
    """Extract a plain-text prompt from an OpenAI Responses API request body."""
    # Try "input" field (Responses API)
    input_field = body.get("input")
    if isinstance(input_field, str):
        return input_field

    if isinstance(input_field, list):
        parts = []
        for item in input_field:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                role = item.get("role", "")
                content = item.get("content", "")
                if isinstance(content, str):
                    parts.append(f"[{role}]: {content}" if role else content)
                elif isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "input_text":
                            parts.append(c.get("text", ""))
                        elif isinstance(c, str):
                            parts.append(c)
        return "\n\n".join(parts)

    # Try "messages" field (Chat Completions API fallback)
    messages = body.get("messages", [])
    if messages:
        parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(f"[{role}]: {content}" if role else content)
        return "\n\n".join(parts)

    # Try "prompt" field (simple)
    return body.get("prompt", "")


def format_response_event(event_type: str, data: dict) -> str:
    """Format a single SSE event."""
    import json
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"
