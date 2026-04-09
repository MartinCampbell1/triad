from pathlib import Path

from scripts.generate_stream_event_contract import (
    main as generate_stream_event_contract,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "desktop" / "src" / "lib" / "stream-event-contract.ts"


def test_generated_stream_event_contract_is_up_to_date():
    before = OUTPUT_PATH.read_text(encoding="utf-8")
    generate_stream_event_contract()
    after = OUTPUT_PATH.read_text(encoding="utf-8")
    assert after == before
