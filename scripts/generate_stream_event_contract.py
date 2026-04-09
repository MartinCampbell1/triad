from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "stream-event.schema.json"
OUTPUT_PATH = REPO_ROOT / "desktop" / "src" / "lib" / "stream-event-contract.ts"


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_version = int(schema.get("schema_version") or 1)
    aliases = dict(schema.get("aliases") or {})
    event_types = [
        str(entry["type"])
        for entry in list(schema.get("event_types") or [])
        if isinstance(entry, dict) and entry.get("type")
    ]
    groups = dict(schema.get("groups") or {})

    content = """// Generated from schemas/stream-event.schema.json by scripts/generate_stream_event_contract.py\n"""
    content += f"export const STREAM_SCHEMA_VERSION = {schema_version} as const;\n\n"
    content += (
        "export const STREAM_EVENT_ALIASES = "
        + json.dumps(aliases, indent=2, ensure_ascii=False)
        + " as const;\n\n"
    )
    content += (
        "export const STREAM_EVENT_TYPES = "
        + json.dumps(event_types, indent=2, ensure_ascii=False)
        + " as const;\n"
    )
    content += (
        "export type CanonicalStreamEventType = typeof STREAM_EVENT_TYPES[number];\n\n"
    )
    for key, value in groups.items():
        const_name = key.upper()
        content += (
            f"export const {const_name} = "
            + json.dumps(value, indent=2, ensure_ascii=False)
            + " as const;\n"
        )

    OUTPUT_PATH.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
