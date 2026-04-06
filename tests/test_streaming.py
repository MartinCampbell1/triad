import pytest
from triad.core.providers.claude import ClaudeAdapter
from triad.core.providers.base import StreamEvent


def test_stream_event_text():
    e = StreamEvent(kind="text", text="hello")
    assert e.kind == "text"
    assert e.text == "hello"


def test_stream_event_done():
    e = StreamEvent(kind="done")
    assert e.kind == "done"
    assert e.text == ""


def test_stream_event_with_data():
    e = StreamEvent(kind="tool_use", data={"name": "Write", "path": "/tmp/x"})
    assert e.data["name"] == "Write"


def test_claude_stream_json_delta_parsed_to_text():
    adapter = ClaudeAdapter()
    events = adapter.parse_stream_line('{"type":"content_block_delta","delta":{"type":"text_delta","text":"hello"}}')
    assert [event.text for event in events] == ["hello"]


def test_claude_stream_json_error_parsed():
    adapter = ClaudeAdapter()
    events = adapter.parse_stream_line('{"type":"error","error":{"message":"boom"}}')
    assert len(events) == 1
    assert events[0].kind == "error"
    assert events[0].text == "boom"
