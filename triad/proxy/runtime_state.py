"""Thread runtime state with compacted continuity across providers."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from triad.proxy.compact_runtime import (
    CompactConfig,
    RestoreContext,
    render_full_summary,
    render_micro_summary,
    render_session_memory,
    render_turns,
    should_full_compact,
    should_microcompact,
    should_session_compact,
)
from triad.proxy.translator import PromptTurn


def _clean_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _turn_to_dict(turn: PromptTurn) -> dict[str, str]:
    return {"role": turn.role, "text": turn.text}


def _turn_from_dict(data: dict) -> PromptTurn:
    return PromptTurn(role=str(data.get("role", "")), text=str(data.get("text", "")))


def _slugify_thread_key(thread_key: str) -> str:
    digest = hashlib.sha1(thread_key.encode("utf-8")).hexdigest()
    return digest[:16]


@dataclass
class ThreadState:
    thread_key: str
    turns: list[PromptTurn] = field(default_factory=list)
    microcompact: str = ""
    session_memory: str = ""
    full_compact: str = ""
    restore_bundle: RestoreContext = field(default_factory=RestoreContext)
    last_provider: str | None = None
    last_profile_name: str | None = None
    last_workdir: str | None = None
    last_response_id: str | None = None
    response_ids: list[str] = field(default_factory=list)
    compact_generation: int = 0
    transcript_path: str | None = None
    summary: str = ""

    def refresh_summary_alias(self) -> None:
        self.summary = self.full_compact or self.session_memory or self.microcompact

    def to_dict(self) -> dict:
        self.refresh_summary_alias()
        return {
            "thread_key": self.thread_key,
            "turns": [_turn_to_dict(turn) for turn in self.turns],
            "microcompact": self.microcompact,
            "session_memory": self.session_memory,
            "full_compact": self.full_compact,
            "restore_bundle": {
                "cwd": self.restore_bundle.cwd,
                "important_files": self.restore_bundle.important_files,
                "active_skills": self.restore_bundle.active_skills,
                "user_directives": self.restore_bundle.user_directives,
                "metadata": self.restore_bundle.metadata,
            },
            "last_provider": self.last_provider,
            "last_profile_name": self.last_profile_name,
            "last_workdir": self.last_workdir,
            "last_response_id": self.last_response_id,
            "response_ids": self.response_ids,
            "compact_generation": self.compact_generation,
            "transcript_path": self.transcript_path,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ThreadState":
        restore_data = data.get("restore_bundle", {}) or {}
        thread = cls(
            thread_key=str(data.get("thread_key", "")),
            turns=[_turn_from_dict(item) for item in data.get("turns", [])],
            microcompact=str(data.get("microcompact", "")),
            session_memory=str(data.get("session_memory", "")),
            full_compact=str(data.get("full_compact", "")),
            restore_bundle=RestoreContext(
                cwd=str(restore_data.get("cwd", "")),
                important_files=list(restore_data.get("important_files", []) or []),
                active_skills=list(restore_data.get("active_skills", []) or []),
                user_directives=list(restore_data.get("user_directives", []) or []),
                metadata=dict(restore_data.get("metadata", {}) or {}),
            ),
            last_provider=data.get("last_provider"),
            last_profile_name=data.get("last_profile_name"),
            last_workdir=data.get("last_workdir"),
            last_response_id=data.get("last_response_id"),
            response_ids=list(data.get("response_ids", []) or []),
            compact_generation=int(data.get("compact_generation", 0) or 0),
            transcript_path=data.get("transcript_path"),
            summary=str(data.get("summary", "")),
        )
        thread.refresh_summary_alias()
        return thread


class ThreadRuntimeStore:
    def __init__(
        self,
        *,
        storage_dir: Path | None = None,
        compact_config: CompactConfig | None = None,
        max_recent_turns: int | None = None,
        max_summary_chars: int | None = None,
    ):
        self.storage_dir = Path(storage_dir).expanduser() if storage_dir else None
        self.storage_dir.mkdir(parents=True, exist_ok=True) if self.storage_dir else None

        config = compact_config or CompactConfig()
        if max_recent_turns is not None:
            config.prompt_recent_turns = max_recent_turns
        if max_summary_chars is not None:
            config.max_full_chars = max_summary_chars
        self.config = config

        self.threads: dict[str, ThreadState] = {}
        self.response_to_thread: dict[str, str] = {}
        self._load_snapshots()

    def resolve_thread_key(
        self,
        *,
        explicit_thread_key: str | None = None,
        previous_response_id: str | None = None,
        fallback_response_id: str,
    ) -> str:
        explicit = str(explicit_thread_key or "").strip()
        if explicit:
            self._ensure_thread(explicit)
            return explicit

        previous = str(previous_response_id or "").strip()
        if previous and previous in self.response_to_thread:
            return self.response_to_thread[previous]

        thread_key = f"thread:{fallback_response_id}"
        self._ensure_thread(thread_key)
        return thread_key

    def register_response(self, thread_key: str, response_id: str) -> None:
        thread = self._ensure_thread(thread_key)
        thread.last_response_id = response_id
        if response_id not in thread.response_ids:
            thread.response_ids.append(response_id)
        self.response_to_thread[response_id] = thread_key
        self._persist_thread(thread)

    def record_request_context(
        self,
        thread_key: str,
        *,
        cwd: str | None = None,
        metadata: dict | None = None,
        turns: list[PromptTurn] | None = None,
    ) -> None:
        thread = self._ensure_thread(thread_key)
        if cwd:
            thread.last_workdir = str(cwd)
        thread.restore_bundle.update(cwd=cwd, metadata=metadata, turns=turns)
        self._persist_thread(thread)

    def record_user_turn(self, thread_key: str, text: str) -> None:
        self._append_turn(thread_key, "user", text)

    def record_assistant_turn(self, thread_key: str, text: str) -> None:
        self._append_turn(thread_key, "assistant", text)

    def mark_provider(self, thread_key: str, provider: str, profile_name: str) -> None:
        thread = self._ensure_thread(thread_key)
        thread.last_provider = provider
        thread.last_profile_name = profile_name
        self._persist_thread(thread)

    def build_prompt(
        self,
        thread_key: str,
        *,
        provider: str,
        current_user_turn: str,
        fallback_prompt: str,
        cwd: str | None = None,
    ) -> str:
        thread = self._ensure_thread(thread_key)
        if cwd:
            thread.last_workdir = str(cwd)
            thread.restore_bundle.update(cwd=cwd)
        thread.refresh_summary_alias()

        if (
            not thread.summary
            and not thread.turns
            and not thread.last_provider
            and not thread.last_response_id
        ):
            return fallback_prompt

        parts = ["Continue the same discussion thread without losing prior decisions, constraints, or active work."]
        if thread.last_provider and thread.last_provider != provider:
            parts.append(
                f"Provider handoff: the previous assistant provider was {thread.last_provider}. "
                "Preserve intent, decisions, constraints, unfinished work, and naming."
            )
        restore = thread.restore_bundle.render()
        if restore:
            parts.append(f"Runtime restore bundle:\n{restore}")
        if thread.full_compact:
            parts.append(f"Full compact summary:\n{thread.full_compact}")
        if thread.session_memory:
            parts.append(f"Session memory:\n{thread.session_memory}")
        if thread.microcompact:
            parts.append(f"Microcompact notes:\n{thread.microcompact}")

        recent = thread.turns[-self.config.prompt_recent_turns :]
        if recent:
            parts.append(f"Most recent turns:\n{render_turns(recent)}")
        if thread.transcript_path:
            parts.append(
                f"If specific earlier details are needed, consult the full transcript at: {thread.transcript_path}"
            )
        parts.append(f"Current user request:\n{current_user_turn}")
        return "\n\n".join(part for part in parts if part).strip()

    def _ensure_thread(self, thread_key: str) -> ThreadState:
        thread = self.threads.get(thread_key)
        if thread is None:
            thread = ThreadState(thread_key=thread_key)
            thread.transcript_path = str(self._transcript_path(thread_key)) if self.storage_dir else None
            self.threads[thread_key] = thread
        return thread

    def _append_turn(self, thread_key: str, role: str, text: str) -> None:
        clean = _clean_text(text)
        if not clean:
            return
        thread = self._ensure_thread(thread_key)
        turn = PromptTurn(role=role, text=clean)
        thread.turns.append(turn)
        thread.restore_bundle.update(cwd=thread.last_workdir, turns=[turn])
        self._append_transcript_event(thread, turn)
        self._compact_thread(thread)
        self._persist_thread(thread)

    def _compact_thread(self, thread: ThreadState) -> None:
        changed = False
        if should_microcompact(thread.turns, self.config):
            overflow = thread.turns[:-self.config.micro_keep_turns]
            if overflow:
                thread.turns = thread.turns[-self.config.micro_keep_turns :]
                thread.microcompact = render_micro_summary(
                    thread.microcompact,
                    overflow,
                    max_chars=self.config.max_micro_chars,
                )
                thread.compact_generation += 1
                changed = True

        if should_session_compact(
            micro_summary=thread.microcompact,
            turns=thread.turns,
            config=self.config,
        ):
            thread.session_memory = render_session_memory(
                thread.session_memory,
                micro_summary=thread.microcompact,
                turns=thread.turns,
                restore_context=thread.restore_bundle,
                max_chars=self.config.max_session_chars,
            )
            thread.microcompact = ""
            thread.compact_generation += 1
            changed = True

        if should_full_compact(
            session_memory=thread.session_memory,
            micro_summary=thread.microcompact,
            turns=thread.turns,
            config=self.config,
        ):
            thread.full_compact = render_full_summary(
                thread.full_compact,
                session_memory=thread.session_memory,
                micro_summary=thread.microcompact,
                restore_context=thread.restore_bundle,
                recent_turns=thread.turns,
                max_chars=self.config.max_full_chars,
            )
            thread.session_memory = ""
            thread.microcompact = ""
            thread.turns = thread.turns[-self.config.prompt_recent_turns :]
            thread.compact_generation += 1
            changed = True

        if changed:
            thread.refresh_summary_alias()

    def _snapshot_path(self, thread_key: str) -> Path:
        assert self.storage_dir is not None
        return self.storage_dir / f"{_slugify_thread_key(thread_key)}.json"

    def _transcript_path(self, thread_key: str) -> Path:
        assert self.storage_dir is not None
        return self.storage_dir / f"{_slugify_thread_key(thread_key)}.jsonl"

    def _append_transcript_event(self, thread: ThreadState, turn: PromptTurn) -> None:
        if not self.storage_dir:
            return
        transcript_path = self._transcript_path(thread.thread_key)
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "role": turn.role,
            "text": turn.text,
            "thread_key": thread.thread_key,
        }
        with transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        thread.transcript_path = str(transcript_path)

    def _persist_thread(self, thread: ThreadState) -> None:
        if not self.storage_dir:
            return
        snapshot_path = self._snapshot_path(thread.thread_key)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            json.dumps(thread.to_dict(), ensure_ascii=True, sort_keys=True, indent=2),
            encoding="utf-8",
        )

    def _load_snapshots(self) -> None:
        if not self.storage_dir or not self.storage_dir.exists():
            return
        for snapshot_path in sorted(self.storage_dir.glob("*.json")):
            try:
                data = json.loads(snapshot_path.read_text(encoding="utf-8"))
                thread = ThreadState.from_dict(data)
            except Exception:
                continue
            self.threads[thread.thread_key] = thread
            for response_id in thread.response_ids:
                self.response_to_thread[response_id] = thread.thread_key
