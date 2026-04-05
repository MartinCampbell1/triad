"""SSE streaming utilities for the proxy."""
from __future__ import annotations

import json


def sse_event(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def sse_done() -> str:
    """Format the [DONE] terminator."""
    return "data: [DONE]\n\n"
