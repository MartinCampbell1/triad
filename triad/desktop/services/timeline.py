from __future__ import annotations

from typing import Any


async def build_session_timeline(runtime: Any, session_id: str) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    events = await runtime._get_session_events(session_id, limit=2000)
    for event in events:
        event_type = str(event.get("type", ""))
        data = event.get("data") or {}
        timestamp = runtime._format_ts(event.get("ts") or event.get("timestamp"))
        base = {
            "id": f"timeline_{event['id']}",
            "session_id": session_id,
            "ts": timestamp,
        }
        if event.get("provider"):
            base["provider"] = event.get("provider")
        if event.get("run_id"):
            base["run_id"] = event.get("run_id")
        if event.get("role"):
            base["role"] = event.get("role")

        if event_type == "user.message":
            content = str(data.get("content") or event.get("content") or "").strip()
            attachments = [dict(item) for item in data.get("attachments", []) if isinstance(item, dict)]
            if content or attachments:
                item = {**base, "kind": "user_message", "text": content}
                if attachments:
                    item["attachments"] = attachments
                timeline.append(item)
        elif event_type == "message_finalized":
            content = str(data.get("content") or event.get("content") or "").strip()
            if content:
                timeline.append(
                    {
                        **base,
                        "kind": "assistant_message",
                        "text": content,
                        "status": "done",
                    }
                )
        elif event_type == "system":
            body = str(data.get("content") or event.get("content") or "").strip()
            if body:
                item = {
                    **base,
                    "kind": "system_notice",
                    "level": "info",
                    "body": body,
                }
                title = data.get("title")
                if title:
                    item["title"] = str(title)
                timeline.append(item)
        elif event_type in {"tool_use", "tool_result"}:
            tool = str(data.get("tool") or "tool").strip() or "tool"
            raw_input = data.get("input")
            timeline.append(
                {
                    **base,
                    "kind": "tool_call",
                    "tool": tool,
                    "input": raw_input if isinstance(raw_input, (dict, str)) else None,
                    "output": data.get("output"),
                    "status": str(
                        data.get("status")
                        or (
                            "running"
                            if event_type == "tool_use"
                            else ("failed" if data.get("success") is False else "completed")
                        )
                    ),
                }
            )
        elif event_type == "review_finding":
            timeline.append(
                {
                    **base,
                    "kind": "review_finding",
                    "severity": str(data.get("severity") or "P2"),
                    "file": str(data.get("file") or ""),
                    "line": data.get("line"),
                    "line_range": data.get("line_range"),
                    "title": str(data.get("title") or "Finding"),
                    "explanation": str(data.get("explanation") or ""),
                }
            )
        elif event_type == "diff_snapshot":
            patch = str(data.get("patch") or "")
            if patch or data.get("diff_stat"):
                item = {
                    **base,
                    "kind": "diff_snapshot",
                    "patch": patch,
                }
                if data.get("diff_stat"):
                    item["diff_stat"] = str(data.get("diff_stat"))
                timeline.append(item)
        elif event_type == "run_failed":
            body = str(data.get("error") or event.get("content") or "Run failed").strip()
            if body:
                timeline.append(
                    {
                        **base,
                        "kind": "system_notice",
                        "level": "error",
                        "title": "Run failed",
                        "body": body,
                    }
                )
    return timeline
