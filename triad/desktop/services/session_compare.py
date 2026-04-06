from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .timeline import build_session_timeline


TimelineLike = dict[str, Any]


def _trim_excerpt(value: str, limit: int = 160) -> str:
    compact = " ".join(value.split()).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def summarize_timeline_item(item: TimelineLike) -> dict[str, Any]:
    kind = str(item.get("kind") or "system_notice")
    if kind == "user_message":
        attachments = item.get("attachments") if isinstance(item.get("attachments"), list) else []
        text = str(item.get("text") or "")
        excerpt = text
        if attachments and not excerpt.strip():
            excerpt = ", ".join(str(attachment.get("name") or "attachment") for attachment in attachments[:3])
        return {
            "kind": kind,
            "label": "User message",
            "excerpt": _trim_excerpt(excerpt),
        }
    if kind == "assistant_message":
        status = str(item.get("status") or "done")
        label = "Assistant message"
        if status == "streaming":
            label = "Assistant streaming"
        if status == "error":
            label = "Assistant error"
        return {
            "kind": kind,
            "label": label,
            "excerpt": _trim_excerpt(str(item.get("text") or "")),
        }
    if kind == "system_notice":
        title = str(item.get("title") or "System notice").strip() or "System notice"
        return {
            "kind": kind,
            "label": title,
            "excerpt": _trim_excerpt(str(item.get("body") or "")),
        }
    if kind == "tool_call":
        tool = str(item.get("tool") or "Tool").strip() or "Tool"
        status = str(item.get("status") or "running").strip() or "running"
        raw_excerpt = item.get("output")
        if raw_excerpt in (None, ""):
            raw_excerpt = item.get("input")
        excerpt = raw_excerpt if isinstance(raw_excerpt, str) else json.dumps(raw_excerpt or {}, ensure_ascii=False)
        return {
            "kind": kind,
            "label": f"{tool} · {status}",
            "excerpt": _trim_excerpt(excerpt),
        }
    if kind == "review_finding":
        severity = str(item.get("severity") or "P2").strip() or "P2"
        title = str(item.get("title") or "Finding").strip() or "Finding"
        file_path = str(item.get("file") or "").strip()
        excerpt = title if not file_path else f"{file_path} · {title}"
        return {
            "kind": kind,
            "label": f"{severity} finding",
            "excerpt": _trim_excerpt(excerpt),
        }
    if kind == "diff_snapshot":
        return {
            "kind": kind,
            "label": "Diff snapshot",
            "excerpt": _trim_excerpt(str(item.get("diff_stat") or item.get("patch") or "")),
        }
    return {
        "kind": kind,
        "label": kind.replace("_", " ").title(),
    }


def _fingerprint(item: TimelineLike | None) -> str | None:
    if item is None:
        return None
    payload = {
        "kind": item.get("kind"),
        "summary": summarize_timeline_item(item),
        "attachments": [
            {
                "name": attachment.get("name"),
                "path": str(Path(str(attachment.get("path") or "")).name),
            }
            for attachment in (item.get("attachments") if isinstance(item.get("attachments"), list) else [])
            if isinstance(attachment, dict)
        ],
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _kind_counts(items: list[TimelineLike]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in items:
        counter[str(item.get("kind") or "unknown")] += 1
    return dict(counter)


def _build_session_payload(runtime: Any, session_id: str) -> Any:
    return runtime.get_session(session_id)


async def build_session_compare(
    runtime: Any,
    left_session_id: str,
    right_session_id: str,
) -> dict[str, Any]:
    left_payload = await _build_session_payload(runtime, left_session_id)
    right_payload = await _build_session_payload(runtime, right_session_id)
    left_timeline = list(left_payload.get("timeline") or [])
    right_timeline = list(right_payload.get("timeline") or [])
    shared_prefix_count = 0
    diverged = False
    rows: list[dict[str, Any]] = []

    for index in range(max(len(left_timeline), len(right_timeline))):
        left_item = left_timeline[index] if index < len(left_timeline) else None
        right_item = right_timeline[index] if index < len(right_timeline) else None

        if left_item is not None and right_item is not None:
            status = "same" if _fingerprint(left_item) == _fingerprint(right_item) else "different"
        elif left_item is not None:
            status = "left_only"
        else:
            status = "right_only"

        if status == "same" and not diverged:
            shared_prefix_count += 1
        else:
            diverged = True

        rows.append(
            {
                "index": index,
                "status": status,
                "left": left_item,
                "right": right_item,
                "left_summary": summarize_timeline_item(left_item) if left_item is not None else None,
                "right_summary": summarize_timeline_item(right_item) if right_item is not None else None,
            }
        )

    return {
        "left_session": left_payload["session"],
        "right_session": right_payload["session"],
        "overview": {
            "left_total": len(left_timeline),
            "right_total": len(right_timeline),
            "shared_prefix_count": shared_prefix_count,
            "left_counts": _kind_counts(left_timeline),
            "right_counts": _kind_counts(right_timeline),
        },
        "rows": rows,
    }


async def compare_sessions(
    runtime: Any,
    left_session_id: str,
    right_session_id: str,
) -> dict[str, Any]:
    return await build_session_compare(runtime, left_session_id, right_session_id)


async def build_session_replay(runtime: Any, session_id: str) -> dict[str, Any]:
    session_payload = await _build_session_payload(runtime, session_id)
    timeline = list(session_payload.get("timeline") or [])
    counts: Counter[str] = Counter()
    frames: list[dict[str, Any]] = []
    markers: list[dict[str, Any]] = []

    for index, item in enumerate(timeline):
        kind = str(item.get("kind") or "unknown")
        counts[kind] += 1
        summary = summarize_timeline_item(item)
        frames.append(
            {
                "index": index,
                "step": index + 1,
                "ts": item.get("ts"),
                "summary": summary,
                "item": item,
                "counts": dict(counts),
            }
        )
        markers.append(
            {
                "index": index,
                "kind": kind,
                "ts": item.get("ts"),
                "label": summary.get("label"),
            }
        )

    return {
        "session": session_payload["session"],
        "timeline": timeline,
        "total_frames": len(frames),
        "frames": frames,
        "markers": markers,
    }


async def build_session_timeline_for_compare(runtime: Any, session_id: str) -> list[dict[str, Any]]:
    return await build_session_timeline(runtime, session_id)
