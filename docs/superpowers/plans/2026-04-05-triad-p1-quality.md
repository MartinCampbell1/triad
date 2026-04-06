# Triad P1 Quality — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 12 P1 quality issues from GPT-5.4 audit — streaming, session continuity, worktree cleanup, ledger safety, blackboard serialization, rate-limit tracking, CLI --mode flag, config paths, delegate status accuracy.

**Architecture:** Targeted fixes to existing modules. Each task is independent and committed separately.

**Tech Stack:** Python 3.12+, asyncio, aiosqlite

---

## Task 1: Streaming execute (P1-1)

**Files:**
- Modify: `triad/core/providers/base.py`
- Create: `tests/test_streaming.py`

Add `StreamEvent` dataclass and `execute_stream()` async generator to `ProviderAdapter`. Keep existing `execute()` as a convenience wrapper that collects stream events.

**StreamEvent:**
```python
@dataclass
class StreamEvent:
    kind: str  # "start", "text", "tool_use", "error", "done"
    text: str = ""
    data: dict | None = None
```

**execute_stream():** reads stdout line-by-line from subprocess, yields StreamEvent per line. **execute()** wraps it by collecting all text events into stdout.

---

## Task 2: Blackboard serialization fix (P1-9)

**Files:**
- Modify: `triad/core/context/blackboard.py`
- Modify: `tests/test_blackboard.py`

Add `accepted_constraints` to `to_dict()` and `from_dict()`. Currently missing — constraints silently disappear on round-trip.

---

## Task 3: Critic rate-limit tracking (P1-10)

**Files:**
- Modify: `triad/core/modes/critic.py`

After each provider execution in `run_round()`, call `account_manager.mark_success()` or `mark_rate_limited()` based on result. Requires passing `account_manager` to CriticMode.

---

## Task 4: Delegate status accuracy (P1-4)

**Files:**
- Modify: `triad/core/modes/delegate.py`

After `asyncio.gather`, check results for exceptions. Set session status to `partial_failure` if any task failed, `failed` if all failed, `completed` only if all succeeded.

---

## Task 5: Ledger seq race fix (P1-6)

**Files:**
- Modify: `triad/core/storage/ledger.py`
- Modify: `tests/test_ledger.py`

Add `UNIQUE(session_id, seq)` constraint. Use atomic `INSERT ... SELECT COALESCE(MAX(seq),0)+1` in a single statement to prevent races.

---

## Task 6: Worktree cleanup (P1-5)

**Files:**
- Modify: `triad/core/worktrees.py`
- Modify: `triad/cli.py`
- Create: `tests/test_worktree_cleanup.py`

Add `cleanup()` method to WorktreeManager. Add `triad worktrees prune` CLI command. Delegate mode calls cleanup after completion.

---

## Task 7: CLI --mode flag (P1-11)

**Files:**
- Modify: `triad/cli.py`
- Modify: `triad/tui/app.py`

Pass `--mode` to TriadApp, which starts the appropriate screen instead of always showing MainScreen.

---

## Task 8: Hardcoded paths → config (P1-8)

**Files:**
- Modify: `triad/cli.py`

Replace `Path.home() / ".cli-profiles"` and `Path.home() / ".triad"` in CLI commands with `load_config()` values.

---

## Task 9: Session continuity — remove dead field (P1-2, P1-3)

**Files:**
- Modify: `triad/core/modes/critic.py`

Remove `_writer_session_id` field that's never assigned. Add TODO comment for future session continuity implementation. Honest code > pretend features.

---

## Task 10: Codex profile validation (P1-7)

**Files:**
- Modify: `triad/core/accounts/manager.py`

Relax Codex validator: accept profile if directory contains `auth.json` OR any `.json` config file OR a `home/` directory with codex config.

---

## Task 11: Mode lifecycle cleanup (P1-12)

**Files:**
- Modify: `triad/tui/screens/critic.py`

Call `self._critic_mode.close()` on screen exit (action_stop, screen dismiss). Ensure ledger is always closed.

---

## Task 12: Final P1 verification

Run full test suite with coverage. Tag `v0.3.0-p1-quality`.
