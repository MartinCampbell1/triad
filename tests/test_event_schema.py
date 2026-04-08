import json
from pathlib import Path

import pytest

from triad.desktop.event_schema import (
    SCHEMA_VERSION,
    canonical_event_type,
    normalize_stream_event,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "stream-events"
TRACE_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "stream-traces"


def test_aliases_are_canonicalized():
    assert canonical_event_type("message_delta") == "text_delta"
    assert canonical_event_type("message_completed") == "message_finalized"
    assert canonical_event_type("tool_started") == "tool_use"
    assert canonical_event_type("tool_finished") == "tool_result"


@pytest.mark.parametrize(
    "fixture_path",
    sorted(FIXTURES_DIR.glob("*.json")),
    ids=lambda path: path.stem,
)
def test_fixture_events_match_schema(fixture_path: Path):
    event = json.loads(fixture_path.read_text(encoding="utf-8"))
    normalized = normalize_stream_event(event)
    assert normalized["schema_version"] == SCHEMA_VERSION
    assert normalized["type"] == event["type"]


@pytest.mark.parametrize(
    "fixture_path",
    sorted(TRACE_FIXTURES_DIR.glob("*.jsonl")),
    ids=lambda path: path.stem,
)
def test_trace_fixtures_are_schema_valid(fixture_path: Path):
    lines = fixture_path.read_text(encoding="utf-8").splitlines()
    assert lines, "trace fixtures must contain at least one event"
    for line in lines:
        normalized = normalize_stream_event(json.loads(line))
        assert normalized["schema_version"] == SCHEMA_VERSION


def test_diff_snapshot_aliases_are_normalized():
    event = normalize_stream_event(
        {
            "session_id": "sess_diff",
            "type": "diff_snapshot",
            "path": "desktop/src/lib/rpc.ts",
            "old_string": "old",
            "new_string": "new",
        }
    )
    assert event["old_text"] == "old"
    assert event["new_text"] == "new"


def test_tool_use_defaults_to_running_status():
    event = normalize_stream_event(
        {
            "session_id": "sess_tool",
            "type": "tool_use",
            "tool": "Read",
        }
    )
    assert event["status"] == "running"


def test_tool_result_defaults_to_completed_status():
    event = normalize_stream_event(
        {
            "session_id": "sess_tool",
            "type": "tool_result",
            "tool": "Read",
        }
    )
    assert event["status"] == "completed"
