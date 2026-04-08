from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    ".github/workflows/python-ci.yml",
    ".github/workflows/frontend-ci.yml",
    ".github/workflows/desktop-smoke.yml",
    ".github/workflows/desktop-e2e.yml",
    ".github/workflows/release-gates.yml",
    "desktop/e2e/recovery.spec.ts",
    "desktop/e2e/shell.spec.ts",
    "desktop/playwright.config.ts",
    "docs/PRODUCT_MAP.md",
    "docs/PARITY_MATRIX.md",
    "schemas/stream-event.schema.json",
    "tests/fixtures/stream-traces/claude-session-send.jsonl",
    "tests/fixtures/stream-traces/critic-round.jsonl",
    "tests/fixtures/stream-traces/codex-session-send.jsonl",
]
CODE_PATHS = [
    REPO_ROOT / "desktop" / "src",
    REPO_ROOT / "triad",
    REPO_ROOT / "scripts",
    REPO_ROOT / ".github" / "workflows",
]
BANNED_PATTERNS = [
    re.compile(r"triad\.desktop\.mock-state", re.IGNORECASE),
    re.compile(r"Running on mock backend", re.IGNORECASE),
    re.compile(r"backendMode\s*===\s*[\"']mock[\"']"),
]
LEGACY_IMPORT_PATTERN = re.compile(r"triad\.(proxy|patcher|tui)")
USER_PATH_PATTERN = re.compile(r"/Users/")
TEXT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".json", ".yml", ".yaml", ".md"}


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for base in CODE_PATHS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in TEXT_EXTENSIONS:
                files.append(path)
    return files


def main() -> int:
    failures: list[str] = []

    for relative_path in REQUIRED_FILES:
        if not (REPO_ROOT / relative_path).exists():
            failures.append(f"Missing required file: {relative_path}")

    for path in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(REPO_ROOT)

        if relative == Path("scripts/release_gates.py"):
            continue

        for pattern in BANNED_PATTERNS:
            if pattern.search(text):
                failures.append(
                    f"Banned mock fallback marker in {relative}: {pattern.pattern}"
                )

        if LEGACY_IMPORT_PATTERN.search(text) and relative.parts[:2] in {
            ("triad", "desktop"),
            ("desktop", "src"),
        }:
            failures.append(
                f"Legacy import leaked into canonical desktop path: {relative}"
            )

        in_canonical_code = relative.parts[:2] in {
            ("triad", "desktop"),
            ("desktop", "src"),
            (".github", "workflows"),
        } or relative.parts[:1] == ("scripts",)
        if USER_PATH_PATTERN.search(text) and in_canonical_code:
            failures.append(f"Hardcoded user path detected in {relative}")

    if failures:
        print("release-gates failed")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("release-gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
