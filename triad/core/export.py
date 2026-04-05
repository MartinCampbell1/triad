"""Session export — JSONL and Markdown formats."""
from __future__ import annotations

import json
import time
from pathlib import Path

from triad.core.storage.ledger import Ledger


async def export_session_jsonl(ledger: Ledger, session_id: str, output_path: Path) -> Path:
    """Export a session as JSONL transcript."""
    session = await ledger.get_session(session_id)
    events = await ledger.get_events(session_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(json.dumps({"type": "session", **session}) + "\n")
        for event in events:
            f.write(json.dumps(event) + "\n")

    return output_path


async def export_session_markdown(ledger: Ledger, session_id: str, output_path: Path) -> Path:
    """Export a session as Markdown report."""
    session = await ledger.get_session(session_id)
    events = await ledger.get_events(session_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    created = time.strftime("%Y-%m-%d %H:%M", time.localtime(session["created_at"]))

    lines = [
        f"# Session Report: {session_id}",
        "",
        f"**Mode:** {session['mode']}",
        f"**Status:** {session['status']}",
        f"**Task:** {session['task']}",
        f"**Created:** {created}",
        "",
        "---",
        "",
        "## Events",
        "",
    ]

    for event in events:
        ts = time.strftime("%H:%M:%S", time.localtime(event["ts"]))
        agent = event.get("agent") or ""
        content = event.get("content") or ""
        lines.append(f"### [{ts}] {event['event_type']} {agent}")
        if content:
            lines.append("")
            lines.append(content[:3000])
        lines.append("")

    output_path.write_text("\n".join(lines))
    return output_path
