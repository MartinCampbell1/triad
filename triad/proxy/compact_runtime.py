"""Compaction helpers for cross-provider thread continuity."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from textwrap import shorten

from triad.proxy.translator import PromptTurn

TOKEN_DIVISOR = 4
TURN_PREVIEW_CHARS = 240
SUMMARY_LINE_CHARS = 280
MAX_IMPORTANT_FILES = 5
MAX_IMPORTANT_SKILLS = 5
MAX_DIRECTIVES = 8

ABSOLUTE_PATH_RE = re.compile(r"(~?/[\w./:@+-]+)")
RELATIVE_PATH_RE = re.compile(r"\b[\w.-]+\.(?:py|js|ts|tsx|jsx|json|toml|yaml|yml|md|sh|rs|go|java|kt|swift|rb)\b")
SKILL_RE = re.compile(r"\$?([A-Za-z0-9_.-]+(?:-skill|skill|checks|openai-docs|imagegen|plugin-creator|skill-creator|skill-installer))")
DIRECTIVE_RE = re.compile(
    r"\b(?:must|should|need to|don't|do not|keep|use|switch|preserve|avoid|priorit(?:y|ize)|fallback)\b",
    re.IGNORECASE,
)


def estimate_tokens(text: str) -> int:
    clean = " ".join(str(text or "").split()).strip()
    if not clean:
        return 0
    return max(1, len(clean) // TOKEN_DIVISOR)


def shorten_line(text: str, width: int = SUMMARY_LINE_CHARS) -> str:
    clean = " ".join(str(text or "").split()).strip()
    if not clean:
        return ""
    return shorten(clean, width=width, placeholder="...")


def merge_unique(existing: list[str], new_items: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in [*existing, *new_items]:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        merged.append(value)
        seen.add(value)
    if len(merged) <= limit:
        return merged
    return merged[-limit:]


def extract_paths(text: str) -> list[str]:
    values: list[str] = []
    for pattern in (ABSOLUTE_PATH_RE, RELATIVE_PATH_RE):
        for match in pattern.findall(text or ""):
            candidate = str(match).rstrip(".,:;)]}")
            if candidate:
                values.append(candidate)
    return merge_unique([], values, limit=MAX_IMPORTANT_FILES)


def extract_skills(text: str) -> list[str]:
    return merge_unique([], [m.group(1) for m in SKILL_RE.finditer(text or "")], limit=MAX_IMPORTANT_SKILLS)


def extract_directives(turns: list[PromptTurn]) -> list[str]:
    directives: list[str] = []
    for turn in turns:
        if turn.role not in {"user", "system", "input"}:
            continue
        for line in str(turn.text or "").splitlines():
            clean = " ".join(line.split()).strip()
            if clean and DIRECTIVE_RE.search(clean):
                directives.append(shorten_line(clean, width=SUMMARY_LINE_CHARS))
    return merge_unique([], directives, limit=MAX_DIRECTIVES)


@dataclass
class RestoreContext:
    cwd: str = ""
    important_files: list[str] = field(default_factory=list)
    active_skills: list[str] = field(default_factory=list)
    user_directives: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def update(
        self,
        *,
        cwd: str | None = None,
        metadata: dict | None = None,
        turns: list[PromptTurn] | None = None,
    ) -> None:
        if cwd:
            self.cwd = str(cwd)
        if isinstance(metadata, dict):
            flattened: dict[str, str] = {}
            for key, value in metadata.items():
                if value is None:
                    continue
                if isinstance(value, (str, int, float, bool)):
                    flattened[str(key)] = str(value)
            self.metadata.update(flattened)

        if not turns:
            return
        text_blob = "\n".join(turn.text for turn in turns)
        self.important_files = merge_unique(
            self.important_files,
            extract_paths(text_blob),
            limit=MAX_IMPORTANT_FILES,
        )
        self.active_skills = merge_unique(
            self.active_skills,
            extract_skills(text_blob),
            limit=MAX_IMPORTANT_SKILLS,
        )
        self.user_directives = merge_unique(
            self.user_directives,
            extract_directives(turns),
            limit=MAX_DIRECTIVES,
        )

    def render(self) -> str:
        sections: list[str] = []
        if self.cwd:
            sections.append(f"Working directory: {self.cwd}")
        if self.important_files:
            files = "\n".join(f"- {path}" for path in self.important_files)
            sections.append(f"Important files and paths:\n{files}")
        if self.active_skills:
            skills = "\n".join(f"- {skill}" for skill in self.active_skills)
            sections.append(f"Active skills and capabilities:\n{skills}")
        if self.user_directives:
            directives = "\n".join(f"- {item}" for item in self.user_directives)
            sections.append(f"Important user directives:\n{directives}")
        return "\n\n".join(sections)


@dataclass
class CompactConfig:
    micro_keep_turns: int = 12
    prompt_recent_turns: int = 6
    micro_threshold_tokens: int = 4_000
    session_threshold_tokens: int = 8_000
    full_threshold_tokens: int = 12_000
    max_micro_chars: int = 3_000
    max_session_chars: int = 4_000
    max_full_chars: int = 6_000


def render_turns(turns: list[PromptTurn]) -> str:
    return "\n".join(f"- {turn.role}: {turn.text}" for turn in turns if turn.text)


def render_micro_summary(previous: str, overflow: list[PromptTurn], *, max_chars: int) -> str:
    lines: list[str] = []
    if previous.strip():
        lines.append(previous.strip())
    lines.extend(
        f"- {turn.role}: {shorten_line(turn.text, width=TURN_PREVIEW_CHARS)}"
        for turn in overflow
        if turn.text
    )
    return "\n".join(line for line in lines if line).strip()[-max_chars:]


def render_session_memory(
    previous: str,
    *,
    micro_summary: str,
    turns: list[PromptTurn],
    restore_context: RestoreContext,
    max_chars: int,
) -> str:
    user_turns = [turn for turn in turns if turn.role in {"user", "input", "system"}]
    primary_request = shorten_line(user_turns[0].text, width=420) if user_turns else ""
    recent_requests = [shorten_line(turn.text, width=200) for turn in user_turns[-6:] if turn.text]
    sections: list[str] = []
    if primary_request:
        sections.append(f"Primary request and intent:\n- {primary_request}")
    if restore_context.user_directives:
        sections.append(
            "Directives to preserve:\n"
            + "\n".join(f"- {item}" for item in restore_context.user_directives)
        )
    if restore_context.important_files:
        sections.append(
            "Relevant files and paths:\n"
            + "\n".join(f"- {path}" for path in restore_context.important_files)
        )
    if micro_summary:
        sections.append(f"Compacted thread history:\n{micro_summary}")
    if recent_requests:
        sections.append(
            "Most recent user requests:\n"
            + "\n".join(f"- {item}" for item in recent_requests)
        )
    if previous.strip():
        sections.insert(0, previous.strip())
    return "\n\n".join(section for section in sections if section).strip()[-max_chars:]


def render_full_summary(
    previous: str,
    *,
    session_memory: str,
    micro_summary: str,
    restore_context: RestoreContext,
    recent_turns: list[PromptTurn],
    max_chars: int,
) -> str:
    sections: list[str] = []
    if previous.strip():
        sections.append(previous.strip())
    sections.append("Primary Request and Intent")
    if session_memory:
        sections.append(session_memory)
    restore = restore_context.render()
    if restore:
        sections.append("Key Runtime Context")
        sections.append(restore)
    if micro_summary:
        sections.append("Compacted Interaction Notes")
        sections.append(micro_summary)
    if recent_turns:
        sections.append("Recent Verbatim Turns")
        sections.append(render_turns(recent_turns[-4:]))
    text = "\n\n".join(section for section in sections if section).strip()
    return text[-max_chars:]


def should_microcompact(turns: list[PromptTurn], config: CompactConfig) -> bool:
    if len(turns) > config.micro_keep_turns:
        return True
    return estimate_tokens(render_turns(turns)) > config.micro_threshold_tokens


def should_session_compact(
    *,
    micro_summary: str,
    turns: list[PromptTurn],
    config: CompactConfig,
) -> bool:
    budget = estimate_tokens(micro_summary) + estimate_tokens(render_turns(turns))
    return budget > config.session_threshold_tokens


def should_full_compact(
    *,
    session_memory: str,
    micro_summary: str,
    turns: list[PromptTurn],
    config: CompactConfig,
) -> bool:
    budget = (
        estimate_tokens(session_memory)
        + estimate_tokens(micro_summary)
        + estimate_tokens(render_turns(turns))
    )
    return budget > config.full_threshold_tokens


def dumps_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True)
