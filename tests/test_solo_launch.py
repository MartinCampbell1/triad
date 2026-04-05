from pathlib import Path


async def test_solo_action_does_not_use_run_until_complete():
    source = Path("/Users/martin/triad/triad/tui/screens/main.py").read_text()
    assert "run_until_complete" not in source


async def test_solo_action_uses_async_pattern():
    source = Path("/Users/martin/triad/triad/tui/screens/main.py").read_text()
    assert "to_thread" in source or "run_worker" in source
