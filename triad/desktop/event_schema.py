"""Canonical stream-event schema helpers shared by desktop producers and consumers."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

SCHEMA_VERSION = 1
CANONICAL_STREAM_EVENT_TYPES = {
    "text_delta",
    "message_finalized",
    "tool_use",
    "tool_result",
    "review_finding",
    "diff_snapshot",
    "stderr",
    "run_completed",
    "run_failed",
    "terminal_output",
    "system",
}

EVENT_TYPE_ALIASES: dict[str, str] = {
    "message_delta": "text_delta",
    "message_completed": "message_finalized",
    "tool_started": "tool_use",
    "tool_finished": "tool_result",
    "completed": "run_completed",
    "error": "run_failed",
    "status": "system",
}


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "stream-event.schema.json"


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(_schema_path().read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def canonical_event_type(raw_type: str | None) -> str:
    normalized = (raw_type or "system").strip() or "system"
    return EVENT_TYPE_ALIASES.get(normalized, normalized)


def normalize_stream_event(raw_event: Mapping[str, Any]) -> dict[str, Any]:
    event = {key: value for key, value in dict(raw_event).items() if value is not None}
    event_type = canonical_event_type(str(event.get("type", "system")))
    session_id = str(event.get("session_id", "")).strip()
    if not session_id:
        raise ValueError("stream events require a non-empty session_id")

    normalized: dict[str, Any] = {
        **event,
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "type": event_type,
    }

    for key in (
        "run_id",
        "provider",
        "role",
        "source",
        "timestamp",
        "message_id",
        "tool",
        "status",
    ):
        if key in normalized and normalized[key] is not None:
            normalized[key] = str(normalized[key])

    if "authoritative" in normalized:
        normalized["authoritative"] = bool(normalized["authoritative"])
    if "success" in normalized:
        normalized["success"] = bool(normalized["success"])
    if "line" in normalized and normalized["line"] not in (None, ""):
        normalized["line"] = int(normalized["line"])

    if event_type == "text_delta":
        normalized["delta"] = str(
            normalized.get("delta") or normalized.get("content") or ""
        )
    elif event_type == "message_finalized":
        normalized["content"] = str(normalized.get("content") or "")
    elif event_type in {"tool_use", "tool_result"}:
        normalized["tool"] = str(normalized.get("tool") or "tool")
        if "status" not in normalized:
            success = normalized.get("success")
            normalized["status"] = (
                "running"
                if event_type == "tool_use"
                else ("failed" if success is False else "completed")
            )
        normalized.setdefault("input", normalized.get("input", {}))
    elif event_type == "review_finding":
        normalized["severity"] = str(normalized.get("severity") or "P2")
        normalized["file"] = str(normalized.get("file") or "")
        normalized["title"] = str(normalized.get("title") or "Finding")
        normalized["explanation"] = str(
            normalized.get("explanation") or normalized.get("content") or ""
        )
        if "line_range" in normalized:
            normalized["line_range"] = str(normalized["line_range"])
    elif event_type == "diff_snapshot":
        normalized["path"] = str(
            normalized.get("path") or normalized.get("file_path") or ""
        )
        normalized["old_text"] = str(
            normalized.get("old_text")
            or normalized.get("oldText")
            or normalized.get("old_string")
            or ""
        )
        normalized["new_text"] = str(
            normalized.get("new_text")
            or normalized.get("newText")
            or normalized.get("new_string")
            or normalized.get("content")
            or ""
        )
    elif event_type == "stderr":
        normalized["data"] = str(
            normalized.get("data") or normalized.get("error") or ""
        )
    elif event_type == "run_failed":
        normalized["error"] = str(
            normalized.get("error") or normalized.get("content") or "Run failed"
        )
    elif event_type == "terminal_output":
        normalized["terminal_id"] = str(normalized.get("terminal_id") or "")
        normalized["data"] = str(normalized.get("data") or "")
    elif event_type == "system":
        normalized["content"] = str(
            normalized.get("content") or normalized.get("message") or ""
        )

    if (
        event_type not in {"stderr", "terminal_output"}
        and "data" in normalized
        and not isinstance(normalized["data"], str)
    ):
        normalized.pop("data", None)

    _validator().validate(normalized)
    return normalized


def validate_stream_event(raw_event: Mapping[str, Any]) -> None:
    normalize_stream_event(raw_event)
