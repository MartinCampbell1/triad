# Triad Desktop Client — Architecture & Implementation Spec

**Date:** 2026-04-06
**Status:** Final Design — approved for implementation
**Author:** Martin + Claude (brainstorm session)

---

## 1. What We're Building

A **macOS desktop AI coding workspace** that looks and feels like the Codex Desktop App, but runs entirely on our own architecture: multi-provider orchestration, persistent sessions, writer/critic loops, worktree isolation, and account rotation.

**Name:** Triad Desktop (working name)
**One-liner:** Codex-inspired desktop shell for multi-provider AI coding sessions.

### 1.1 Core Design Principle

> UI is a Codex-quality experience. Backend is Triad orchestration. They meet at a clean JSON-RPC boundary.

### 1.2 Why Not Patch Codex App

We spent 6+ hours trying to fork/patch the closed Codex Desktop app. The auth/bootstrap/integrity layers made even the first screen impossible. Building our own client is faster, more reliable, and becomes an asset instead of a maintenance trap.

### 1.3 Key Requirements From User

- 95% visual match to Codex Desktop App
- Same layout: sidebar, chat transcript, composer, terminal drawer, diff panel
- Multi-provider: Claude, Codex (15 accounts), Gemini (2 accounts)
- Multi-agent modes: solo, critic, brainstorm, delegate
- Claude uses Max subscription only (NO extra usage, NO `-p` flag)
- Full session history without aggressive compaction
- Project-aware, worktree-isolated execution
- macOS-native feel, daily-driver quality

---

## 2. Tech Stack (Decided)

| Layer | Technology | Why |
|-------|-----------|-----|
| **Desktop shell** | Tauri v2 | Native macOS window, Rust core, ~25MB binary. No Electron bloat. |
| **Frontend** | React 19 + TypeScript | Same stack as Codex. Ecosystem for transcript/diff/terminal. |
| **Styling** | Tailwind CSS 4 + shadcn/ui | Design tokens from extracted Codex CSS. shadcn gives accessible components. |
| **Terminal embed** | xterm.js 5 | Same lib as VS Code. Production-proven terminal emulator. |
| **Diff viewer** | Monaco Editor or react-diff-viewer-continued | Syntax-highlighted unified/split diffs. |
| **Transcript virtualization** | @tanstack/virtual or react-virtuoso | Handle 10k+ messages without lag. |
| **Markdown rendering** | react-markdown + rehype-highlight + remark-gfm | Rich markdown with code blocks, tables, math. |
| **Backend** | Python 3.12+ (existing Triad codebase) | Already has: adapters, accounts, proxy, sessions, worktrees. |
| **UI ↔ Backend bridge** | JSON-RPC over Tauri sidecar (stdio) | Tauri spawns Python backend as child process. Bidirectional JSON messages over stdin/stdout. |
| **Local persistence** | SQLite (via aiosqlite) | Event ledger, sessions, search index. Already in Triad. |
| **Package manager** | pnpm (frontend), uv (Python) | Fast, reliable. |

### 2.1 Project Structure

```
triad/
├── desktop/                    # Tauri v2 + React frontend
│   ├── src-tauri/              # Rust Tauri core
│   │   ├── src/
│   │   │   └── main.rs         # Tauri app, sidecar launch, IPC bridge
│   │   ├── Cargo.toml
│   │   └── tauri.conf.json
│   ├── src/                    # React frontend
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── sidebar/        # Project list, session list, search
│   │   │   ├── transcript/     # Chat messages, tool cards, streaming
│   │   │   ├── composer/       # Input, attachments, mode selector
│   │   │   ├── terminal/       # xterm.js embedded terminal
│   │   │   ├── diff/           # Diff viewer panel
│   │   │   ├── review/         # Findings, severity badges
│   │   │   └── shared/         # Design system, tokens, primitives
│   │   ├── stores/             # Zustand stores for state
│   │   ├── hooks/              # React hooks
│   │   ├── lib/                # Utilities, RPC client
│   │   └── styles/
│   │       ├── tokens.css      # Design tokens from Codex CSS
│   │       └── globals.css
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── triad/                      # Python backend (existing, extended)
│   ├── core/                   # Existing: accounts, config, providers, modes, etc.
│   ├── proxy/                  # Existing: FastAPI proxy, translator
│   ├── desktop/                # NEW: Desktop bridge layer
│   │   ├── bridge.py           # JSON-RPC stdio server for Tauri
│   │   ├── session_manager.py  # Session lifecycle, event ledger
│   │   ├── claude_pty.py       # Claude interactive PTY manager
│   │   ├── hooks_listener.py   # Unix socket listener for Claude hooks
│   │   ├── file_watcher.py     # Watch ~/.claude/ for session updates
│   │   ├── terminal_manager.py # Manage user terminal sessions
│   │   └── orchestrator.py     # Multi-agent mode engine
│   └── ...
│
├── docs/
│   ├── design-tokens.json      # Extracted from Codex CSS
│   ├── DESIGN_SYSTEM.md        # Visual reference for agents
│   └── design-references/      # Screenshots from Codex app
│
└── pyproject.toml
```

---

## 3. Architecture

### 3.1 High-Level Data Flow

```
┌──────────────────────────────────────────────────────────┐
│              Tauri Window (macOS native)                  │
│                                                          │
│  ┌──────────┬──────────────────────────┬──────────────┐  │
│  │ Sidebar  │    Transcript / Diff     │  (optional)  │  │
│  │          │                          │  Review pane │  │
│  │ Projects │  Chat messages           │              │  │
│  │ Sessions │  Tool cards              │  Findings    │  │
│  │ Search   │  Code blocks             │  Severity    │  │
│  │          │  Streaming               │              │  │
│  ├──────────┴──────────────────────────┴──────────────┤  │
│  │ Composer: input + attachments + mode + provider     │  │
│  ├─────────────────────────────────────────────────────┤  │
│  │ Bottom Drawer: Terminal / Logs / Tasks / Diagnostics│  │
│  └─────────────────────────────────────────────────────┘  │
│                          │                                │
│                    Tauri IPC                              │
├──────────────────────────┼───────────────────────────────┤
│              Rust Sidecar Manager                        │
│              (spawns Python backend)                     │
├──────────────────────────┼───────────────────────────────┤
│                   JSON-RPC (stdio)                       │
├──────────────────────────┼───────────────────────────────┤
│              Python Backend (Triad)                       │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Desktop Bridge (JSON-RPC server)                  │  │
│  │    ↓                                               │  │
│  │  Session Manager ←→ Event Ledger (SQLite)          │  │
│  │    ↓                                               │  │
│  │  Orchestrator (solo/critic/brainstorm/delegate)     │  │
│  │    ↓                                               │  │
│  │  Provider Router → Account Manager → Adapters      │  │
│  │                                                    │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐          │  │
│  │  │ Claude   │ │ Codex    │ │ Gemini   │          │  │
│  │  │ PTY+Hooks│ │ headless │ │ headless │          │  │
│  │  │ (subscr.)│ │ (--json) │ │ (API)    │          │  │
│  │  └──────────┘ └──────────┘ └──────────┘          │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Worktree Manager  │  Terminal Manager  │  File Watcher  │
└──────────────────────────────────────────────────────────┘
```

### 3.2 JSON-RPC Bridge Protocol

Tauri (Rust) spawns Python backend as a sidecar process. Communication over stdin/stdout using JSON-RPC 2.0.

**Frontend → Backend (requests):**

```typescript
// Create a new session
{ "jsonrpc": "2.0", "method": "session.create", "params": { "project_path": "/Users/martin/myproject", "mode": "solo", "provider": "claude" }, "id": 1 }

// Send a message
{ "jsonrpc": "2.0", "method": "session.send", "params": { "session_id": "abc123", "content": "Fix the auth bug", "attachments": ["/path/to/file.py"] }, "id": 2 }

// Switch mode
{ "jsonrpc": "2.0", "method": "session.set_mode", "params": { "session_id": "abc123", "mode": "critic", "writer": "claude", "critic": "codex" }, "id": 3 }

// List sessions
{ "jsonrpc": "2.0", "method": "session.list", "params": { "project_path": "/Users/martin/myproject" }, "id": 4 }

// Terminal command
{ "jsonrpc": "2.0", "method": "terminal.create", "params": { "cwd": "/Users/martin/myproject" }, "id": 5 }

// Stop current run
{ "jsonrpc": "2.0", "method": "run.stop", "params": { "run_id": "run_xyz" }, "id": 6 }
```

**Backend → Frontend (notifications, streaming):**

```typescript
// Streaming text delta
{ "jsonrpc": "2.0", "method": "event.stream", "params": { "session_id": "abc123", "run_id": "run_xyz", "type": "text_delta", "provider": "claude", "role": "writer", "delta": "I'll fix the auth bug by..." } }

// Tool use event
{ "jsonrpc": "2.0", "method": "event.stream", "params": { "session_id": "abc123", "run_id": "run_xyz", "type": "tool_use", "provider": "claude", "tool": "Edit", "input": { "file": "api/auth.py", "old_string": "...", "new_string": "..." } } }

// Tool result
{ "jsonrpc": "2.0", "method": "event.stream", "params": { "type": "tool_result", "tool": "Edit", "success": true } }

// Run completed
{ "jsonrpc": "2.0", "method": "event.stream", "params": { "type": "run_completed", "run_id": "run_xyz", "status": "success" } }

// Critic finding
{ "jsonrpc": "2.0", "method": "event.stream", "params": { "type": "review_finding", "severity": "P0", "file": "api/auth.py", "line": 42, "title": "Race condition in session check", "explanation": "..." } }

// Terminal output
{ "jsonrpc": "2.0", "method": "terminal.output", "params": { "terminal_id": "term_1", "data": "base64-encoded-bytes" } }
```

### 3.3 Event Ledger (append-only)

All events are persisted to SQLite before being sent to UI. This enables:
- Crash recovery (replay events to reconstruct state)
- Full history (no compaction as single source of truth)
- Search across sessions
- Session resume after app restart

```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    run_id TEXT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    type TEXT NOT NULL,           -- 'user_message', 'text_delta', 'tool_use', 'tool_result', 
                                  -- 'run_start', 'run_end', 'finding', 'mode_change', etc.
    provider TEXT,                -- 'claude', 'codex', 'gemini'
    role TEXT,                    -- 'writer', 'critic', 'user'
    data JSON NOT NULL,           -- Event-specific payload
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    title TEXT,
    mode TEXT NOT NULL DEFAULT 'solo',
    status TEXT NOT NULL DEFAULT 'active',  -- 'active', 'paused', 'completed'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    provider_config JSON,         -- {"writer": "claude", "critic": "codex"}
    summary TEXT,                 -- Auto-generated, derived from events
    message_count INTEGER DEFAULT 0,
    pinned BOOLEAN DEFAULT FALSE
);

CREATE TABLE projects (
    path TEXT PRIMARY KEY,
    display_name TEXT,
    git_root TEXT,
    last_opened_at TEXT,
    provider_preferences JSON
);

CREATE TABLE worktrees (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    run_id TEXT,
    project_path TEXT NOT NULL,
    worktree_path TEXT NOT NULL,
    branch TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL
);

-- Indexes for fast queries
CREATE INDEX idx_events_session ON events(session_id, timestamp);
CREATE INDEX idx_events_type ON events(type);
CREATE INDEX idx_sessions_project ON sessions(project_path, updated_at DESC);
```

---

## 4. Claude Integration Without `-p` Flag

### 4.1 The Problem

`claude -p --output-format stream-json` gives perfect structured output but may trigger extra usage billing. User wants subscription-only billing.

### 4.2 The Solution: Triple-Source Event Pipeline

Claude runs **interactively** (no `-p` flag) in a hidden PTY. We reconstruct structured events from three complementary sources:

```
Source 1: Hooks API ──────→ Structured tool events (official)
Source 2: PTY Output ─────→ Streaming text (parsed from ANSI)
Source 3: Session Files ──→ Authoritative history (file watcher)
         ↓         ↓         ↓
         └────→ Event Merger ←────┘
                    ↓
              Event Ledger
                    ↓
              React Chat UI (beautiful, Codex-style)
```

#### Source 1: Claude Code Hooks (structured tool events)

Claude Code's official hooks system fires shell commands on every tool use. We configure them to send JSON events to a Unix socket.

**Configuration** (auto-injected by Triad into `~/.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "type": "command",
        "command": "python3 -c \"import socket,sys,json,os; s=socket.socket(socket.AF_UNIX); s.connect('/tmp/triad-hooks.sock'); s.send(json.dumps({'hook':'pre_tool','session_id':os.environ.get('CLAUDE_SESSION_ID',''),'tool':os.environ.get('TOOL_NAME',''),'input':os.environ.get('TOOL_INPUT','')}).encode()+b'\\n'); s.close()\""
      }
    ],
    "PostToolUse": [
      {
        "type": "command",
        "command": "python3 -c \"import socket,sys,json,os; s=socket.socket(socket.AF_UNIX); s.connect('/tmp/triad-hooks.sock'); s.send(json.dumps({'hook':'post_tool','session_id':os.environ.get('CLAUDE_SESSION_ID',''),'tool':os.environ.get('TOOL_NAME',''),'output':os.environ.get('TOOL_OUTPUT','')[:4096]}).encode()+b'\\n'); s.close()\""
      }
    ],
    "Stop": [
      {
        "type": "command",
        "command": "python3 -c \"import socket,json,os; s=socket.socket(socket.AF_UNIX); s.connect('/tmp/triad-hooks.sock'); s.send(json.dumps({'hook':'stop','session_id':os.environ.get('CLAUDE_SESSION_ID','')}).encode()+b'\\n'); s.close()\""
      }
    ]
  }
}
```

**What hooks give us:**
- Tool name (Edit, Read, Bash, Grep, Glob, Write, etc.)
- Tool input (file path, command, search pattern, etc.)
- Tool output (file contents, command output, etc.)
- Session ID
- Timing (pre/post)

**What hooks DON'T give us:**
- Assistant text messages (the actual conversational output)
- Streaming text (token-by-token)
- Thinking/reasoning blocks

#### Source 2: PTY Output Parser (streaming text)

Claude runs in a hidden PTY. We capture raw output, strip ANSI escape codes, and parse text content.

```python
# triad/desktop/claude_pty.py

import asyncio
import re
import pty
import os

ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b[()][AB012]')

class ClaudePTYManager:
    """Manages an interactive Claude Code session in a hidden PTY."""
    
    def __init__(self, workdir: str, event_callback):
        self.workdir = workdir
        self.event_callback = event_callback  # sends events to bridge
        self.master_fd = None
        self.pid = None
        self.buffer = ""
        self._running = False
    
    async def start(self):
        """Launch claude interactively in a PTY."""
        self.pid, self.master_fd = pty.openpty()
        
        child_pid = os.fork()
        if child_pid == 0:
            # Child process
            os.setsid()
            os.dup2(self.master_fd, 0)
            os.dup2(self.master_fd, 1)
            os.dup2(self.master_fd, 2)
            os.chdir(self.workdir)
            os.execvp("claude", ["claude"])
        
        self._running = True
        asyncio.create_task(self._read_loop())
    
    async def send_input(self, text: str):
        """Send user input to Claude's PTY stdin."""
        os.write(self.master_fd, (text + "\n").encode())
    
    async def _read_loop(self):
        """Read PTY output, parse, emit events."""
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                data = await loop.run_in_executor(
                    None, os.read, self.master_fd, 4096
                )
                text = data.decode("utf-8", errors="replace")
                clean = ANSI_ESCAPE.sub("", text)
                
                # Parse and emit text chunks as streaming events
                for line in clean.split("\n"):
                    stripped = line.strip()
                    if stripped and not self._is_ui_chrome(stripped):
                        await self.event_callback({
                            "type": "text_delta",
                            "provider": "claude",
                            "delta": stripped,
                            "source": "pty"
                        })
            except OSError:
                break
    
    def _is_ui_chrome(self, line: str) -> bool:
        """Filter out Ink TUI chrome (spinners, status bars, etc.)."""
        chrome_patterns = [
            "⏳", "●", "◐", "◑", "◒", "◓",  # spinners
            "╭", "╰", "│", "─",               # box drawing
            "Press", "Ctrl+",                   # key hints
        ]
        return any(p in line for p in chrome_patterns)
    
    async def stop(self):
        """Gracefully stop Claude."""
        self._running = False
        os.write(self.master_fd, b"/exit\n")
```

**What PTY parser gives us:**
- Streaming text (assistant's response, token by token)
- Real-time output as it appears

**What it doesn't give us well:**
- Structured tool call data (hooks are better for this)
- Clean message boundaries (file watcher is better)

#### Source 3: Session File Watcher (authoritative history)

Claude Code saves full conversation data to `~/.claude/projects/<hash>/`. We watch for changes and read structured data.

```python
# triad/desktop/file_watcher.py

import asyncio
import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

CLAUDE_DIR = Path.home() / ".claude"

class ClaudeSessionWatcher:
    """Watch Claude's local storage for session updates."""
    
    def __init__(self, event_callback):
        self.event_callback = event_callback
        self.observer = Observer()
        self._known_messages = set()
    
    def start(self):
        handler = _Handler(self._on_change)
        self.observer.schedule(handler, str(CLAUDE_DIR), recursive=True)
        self.observer.start()
    
    async def _on_change(self, path: str):
        """When Claude writes session data, parse and emit."""
        p = Path(path)
        if p.suffix in (".json", ".jsonl"):
            try:
                data = json.loads(p.read_text())
                # Extract messages we haven't seen yet
                messages = self._extract_new_messages(data)
                for msg in messages:
                    await self.event_callback({
                        "type": "authoritative_message",
                        "provider": "claude",
                        "source": "file_watcher",
                        **msg
                    })
            except (json.JSONDecodeError, KeyError):
                pass
    
    def _extract_new_messages(self, data):
        """Extract messages not yet seen from Claude's session data."""
        # Implementation depends on Claude's exact storage format
        # Key fields: role, content, tool_use, tool_result
        messages = []
        for item in data.get("messages", data.get("conversation", [])):
            msg_id = item.get("id", hash(json.dumps(item, sort_keys=True)))
            if msg_id not in self._known_messages:
                self._known_messages.add(msg_id)
                messages.append(item)
        return messages
```

**What file watcher gives us:**
- Complete structured messages (after Claude finishes writing them)
- Authoritative history for resume/search
- Clean message boundaries

#### Event Merger

The three sources feed into a merger that deduplicates and orders events:

```python
# triad/desktop/event_merger.py

class EventMerger:
    """Merge events from hooks, PTY parser, and file watcher."""
    
    def __init__(self, ledger, ui_callback):
        self.ledger = ledger      # SQLite event store
        self.ui_callback = ui_callback  # sends to React via JSON-RPC
        self._streaming_buffer = ""
        self._current_run_id = None
    
    async def handle_event(self, event: dict):
        source = event.get("source", "unknown")
        event_type = event["type"]
        
        if event_type == "text_delta" and source == "pty":
            # Stream to UI immediately for live typing effect
            self._streaming_buffer += event["delta"]
            await self.ui_callback(event)
        
        elif event_type in ("pre_tool", "post_tool") and source == "hooks":
            # Tool events from hooks are authoritative — save and emit
            await self.ledger.append(event)
            await self.ui_callback(self._format_tool_card(event))
        
        elif event_type == "authoritative_message" and source == "file_watcher":
            # Replace streaming buffer with clean final version
            await self.ledger.append(event)
            await self.ui_callback({
                "type": "message_finalized",
                "content": event.get("content"),
                "replaces_streaming": True
            })
            self._streaming_buffer = ""
    
    def _format_tool_card(self, event: dict) -> dict:
        """Format hook event as a UI tool card."""
        return {
            "type": "tool_card",
            "tool": event.get("tool"),
            "input": event.get("input"),
            "output": event.get("output"),
            "status": "completed" if event["hook"] == "post_tool" else "running"
        }
```

### 4.3 How It Looks In Practice

User sends "Fix the auth bug in api/auth.py":

1. **Backend** sends text to Claude PTY via stdin
2. **PTY parser** immediately starts emitting `text_delta` events → UI shows streaming text
3. **Hooks** fire `pre_tool(Read, api/auth.py)` → UI shows "Reading api/auth.py" card
4. **Hooks** fire `post_tool(Read, api/auth.py)` → UI shows file content in card
5. **PTY parser** continues streaming Claude's analysis text
6. **Hooks** fire `pre_tool(Edit, api/auth.py)` → UI shows "Editing api/auth.py" card with diff
7. **Hooks** fire `post_tool(Edit)` → UI marks edit as applied
8. **PTY parser** streams final summary text
9. **File watcher** detects session file update → replaces streamed text with clean formatted version
10. **Event ledger** has full structured record for history/search

All of this renders as a beautiful Codex-style chat — not a terminal.

---

## 5. Multi-Agent Architecture

### 5.1 Provider Role Matrix

| Provider | Solo | Critic Writer | Critic Reviewer | Brainstorm | Delegate |
|----------|------|---------------|-----------------|------------|----------|
| **Claude** (PTY, subscription) | Primary | Writer | Writer | Moderator | Coordinator |
| **Codex** (headless, --json) | — | Reviewer | Writer | Participant | Worker |
| **Gemini** (headless, API) | — | — | — | Ideator | Worker |

Claude is ALWAYS interactive PTY (subscription-safe).
Codex and Gemini are ALWAYS headless (no billing concern).

### 5.2 Critic Mode Flow

```
User → "Fix the auth bug"
  ↓
Orchestrator assigns:
  Writer: Claude (PTY)
  Critic: Codex (headless)
  ↓
Round 1:
  1. Send prompt to Claude PTY → Claude writes code
  2. Collect diff from hooks (Edit events)
  3. Send diff to Codex: `codex exec --json -p "Review this diff: ..."`
  4. Parse Codex JSON output → extract findings
  5. Show in UI: writer output + critic findings
  ↓
If findings.any(severity <= P1):
  Round 2:
  1. Send findings to Claude PTY: "Critic found these issues: ..."
  2. Claude fixes → new diff
  3. Send new diff to Codex for re-review
  4. Repeat until LGTM or max_rounds
  ↓
Done: Show final diff + review summary
```

### 5.3 Brainstorm Mode Flow

```
User → "How should we redesign the auth system?"
  ↓
Orchestrator spawns round-robin:
  1. Gemini (ideator): generates creative ideas
  2. Claude (PTY): analyzes feasibility, adds detail
  3. Codex (headless): critiques, finds edge cases
  ↓
Each round:
  - Previous participant's output fed as context to next
  - Shared context grows
  - UI shows conversation with role badges
  ↓
After N rounds or user stop:
  Claude (PTY) synthesizes final recommendation
```

### 5.4 Delegate Mode Flow

```
User → "Refactor auth, add tests, update docs"
  ↓
Orchestrator splits into parallel tasks:
  Task 1: "Refactor auth" → Codex account #1, worktree #1
  Task 2: "Add tests"     → Codex account #2, worktree #2
  Task 3: "Update docs"   → Gemini account #1, worktree #3
  ↓
All run in parallel. UI shows task table with progress.
  ↓
When all done:
  Claude (PTY) reviews all diffs together
  Merge results
```

---

## 6. UI Components Specification

### 6.1 Window Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Traffic lights │ Project: myproject │ Mode: Solo │ Claude ● │   │
├───────────────┬─────────────────────────────────────────────────┤
│               │                                                 │
│  SIDEBAR      │  TRANSCRIPT (main content area)                 │
│  260px        │                                                 │
│               │  [Claude/Writer]                                │
│  ▶ myproject  │  I'll fix the auth bug. Let me read the file.  │
│    Session 1  │                                                 │
│    Session 2  │  ┌─ Read: api/auth.py ────────────────────┐    │
│  ► other-proj │  │ def authenticate(token):               │    │
│               │  │     if not token: ...                   │    │
│  ─────────    │  └────────────────────────────────────────┘    │
│  🔍 Search    │                                                 │
│               │  The issue is on line 42. I'll fix it:          │
│  PINNED       │                                                 │
│  ─────────    │  ┌─ Edit: api/auth.py ────────────────────┐    │
│  Session X    │  │ - if not token:                        │    │
│               │  │ + if not token or token.expired:       │    │
│               │  └────────────────────────────────────────┘    │
│               │                                                 │
│               │  Fixed. The auth now checks token expiry.       │
│               │                                                 │
│               │  ┌─ [Codex/Critic] ──────────────────────┐    │
│               │  │ ⚠ P1: Missing error handling for      │    │
│               │  │   malformed tokens (line 45)           │    │
│               │  │ ✓ LGTM on the expiry check            │    │
│               │  └────────────────────────────────────────┘    │
│               │                                                 │
├───────────────┴─────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Fix the auth bug and add token expiry check     [Send ▶]  │ │
│ │ 📎 api/auth.py   Mode: [Critic ▾]   Provider: [Claude ▾]  │ │
│ └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ Terminal │ Logs │ Tasks │ Diagnostics                    [▲ ▼] │
│ $ git status                                                    │
│ M api/auth.py                                                   │
│ $                                                               │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Transcript Message Types

Each message in the transcript is a React component. Types:

| Type | Visual | Data Source |
|------|--------|------------|
| **UserMessage** | Gray bubble, user avatar | User input from composer |
| **AssistantText** | Markdown rendered, provider badge | PTY parser → file watcher finalize |
| **ToolCard** | Collapsible card, icon per tool type | Hooks API |
| **DiffCard** | Inline unified diff with syntax highlight | Hooks (Edit tool) |
| **BashCard** | Terminal-style output block | Hooks (Bash tool) |
| **FindingCard** | Severity badge (P0/P1/P2), file/line ref | Critic mode output |
| **ThinkingBlock** | Collapsed accordion, "Thinking..." label | PTY parser |
| **SystemMessage** | Subtle gray text, centered | Mode changes, session events |
| **StreamingText** | Typing animation, cursor blink | PTY parser (live) |

### 6.3 Composer

```
┌─────────────────────────────────────────────────────────────┐
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Multiline input area (auto-expand, max 12 lines)       │ │
│ │ Supports: paste images, drag files, @-mentions          │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ 📎 Attach  │  Mode: [Solo ▾]  │  Writer: [Claude ▾]       │
│            │  Critic: [Codex ▾] (if critic mode)           │
│                                                    [Send ▶] │
│                                             Cmd+Enter       │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd+N` | New session |
| `Cmd+K` | Command palette |
| `Cmd+P` | Project switcher |
| `Cmd+F` | Search in session |
| `Cmd+Shift+F` | Search across all sessions |
| `Cmd+\`` | Toggle terminal drawer |
| `Cmd+Shift+D` | Toggle diff panel |
| `Cmd+Enter` | Send message |
| `Cmd+.` | Stop current run |
| `Cmd+Shift+R` | Retry last run |
| `Cmd+1/2/3` | Switch mode (solo/critic/brainstorm) |
| `Cmd+[/]` | Previous/next session |
| `Escape` | Close drawer/panel |

---

## 7. Backend Modules (what exists vs what to build)

### 7.1 Already Exists in Triad (reuse)

| Module | Path | Status |
|--------|------|--------|
| Provider adapters | `triad/core/providers/` | Claude, Codex, Gemini adapters |
| Account manager | `triad/core/accounts/manager.py` | Pool rotation, cooldown, health |
| Config | `triad/core/config.py` | YAML config, paths, profiles |
| Worktree manager | `triad/core/worktrees.py` | Create/cleanup git worktrees |
| Execution policy | `triad/core/execution_policy.py` | Read-only, sandbox modes |
| Session ledger | `triad/core/storage/ledger.py` | SQLite via aiosqlite |
| Proxy server | `triad/proxy/server.py` | FastAPI, OpenAI API translation |
| Critic mode | `triad/core/modes/critic.py` | Writer/critic loop |
| CLI | `triad/cli.py` | Typer commands |

### 7.2 New Modules Needed

| Module | Path | Purpose |
|--------|------|---------|
| **Desktop bridge** | `triad/desktop/bridge.py` | JSON-RPC stdio server, main entry point for Tauri |
| **Claude PTY** | `triad/desktop/claude_pty.py` | Interactive Claude in hidden PTY |
| **Hooks listener** | `triad/desktop/hooks_listener.py` | Unix socket for Claude Code hooks |
| **Event merger** | `triad/desktop/event_merger.py` | Combine hooks + PTY + file watcher |
| **File watcher** | `triad/desktop/file_watcher.py` | Watch ~/.claude/ for session data |
| **Terminal manager** | `triad/desktop/terminal_manager.py` | Manage user terminal sessions (xterm.js backend) |
| **Orchestrator** | `triad/desktop/orchestrator.py` | Multi-agent mode engine (extends existing modes) |
| **Search index** | `triad/desktop/search.py` | FTS5 over event ledger |

### 7.3 Modifications to Existing Modules

| Module | Change |
|--------|--------|
| `providers/claude.py` | Add PTY mode alongside headless mode |
| `providers/base.py` | Add `execute_interactive()` method |
| `modes/critic.py` | Integrate with desktop bridge events |
| `storage/ledger.py` | Add events table, FTS5 index |
| `config.py` | Add desktop-specific config (window state, shortcuts) |

---

## 8. Design System Integration

### 8.1 Source of Truth

Design tokens are extracted from Codex Desktop App's CSS bundle at:
`/Users/martin/codex-fork/source/webview/assets/index-CrdGJg1L.css`

Extracted to:
- `docs/design-tokens.json` — machine-readable
- `docs/DESIGN_SYSTEM.md` — human-readable reference

### 8.2 Screenshots Reference

`docs/design-references/` contains annotated screenshots of:
- Sidebar (collapsed/expanded)
- Transcript with various message types
- Composer states
- Terminal drawer
- Diff view
- Model selector
- Settings
- Streaming state
- Tool use cards
- Error states

### 8.3 Component Library

Base: **shadcn/ui** components, restyled with Codex design tokens via Tailwind.

Key components to build:
- `<Sidebar />` — project/session navigation
- `<Transcript />` — virtualized message list
- `<MessageBubble />` — assistant/user message container
- `<ToolCard />` — collapsible tool use display
- `<DiffView />` — syntax-highlighted diff
- `<Composer />` — multiline input + attachments + controls
- `<TerminalDrawer />` — xterm.js wrapper with tabs
- `<ProviderBadge />` — colored provider/role indicator
- `<FindingCard />` — review finding with severity
- `<CommandPalette />` — Cmd+K overlay

---

## 9. Implementation Phases

### Phase 1: Shell + Single Provider (target: working daily-driver for solo Claude)

**Build:**
1. Tauri v2 project scaffold with React/Tailwind/shadcn
2. Apply design tokens, create base component set
3. Sidebar with project open + session list
4. Transcript with virtualized message rendering
5. Composer with send/stop
6. Python desktop bridge (JSON-RPC over stdio)
7. Claude PTY manager (interactive, no -p)
8. Hooks listener (Unix socket)
9. PTY output parser
10. Event merger + ledger
11. Session persistence (create, list, resume)
12. Basic streaming text display

**Exit criteria:** Open project → create session → chat with Claude → see beautiful formatted output → restart app → resume session.

### Phase 2: Terminal + Diff + Codex Integration

**Build:**
1. xterm.js terminal drawer with tabs
2. Terminal manager in Python backend
3. Diff panel (Monaco or react-diff-viewer)
4. File attachment in composer
5. Codex adapter integration (headless --json)
6. Provider switcher in composer
7. Account rotation for Codex
8. Tool cards (Read, Edit, Bash, Grep, etc.)
9. Project-aware search (FTS5)
10. Command palette (Cmd+K)

**Exit criteria:** Full coding workflow — chat, terminal, diffs, switch providers, search history.

### Phase 3: Multi-Agent Modes

**Build:**
1. Critic mode: Claude writer + Codex reviewer
2. Round management (auto-iterate until LGTM)
3. Finding cards with severity badges
4. Human intervention between rounds
5. Brainstorm mode: round-robin multi-provider
6. Delegate mode: parallel tasks in worktrees
7. Mode selector in composer
8. Worktree visualization
9. Gemini adapter integration

**Exit criteria:** Run critic loop, see findings, iterate. Brainstorm with 3 providers. Delegate parallel tasks.

### Phase 4: Polish + Daily-Driver Quality

**Build:**
1. Session file watcher (authoritative history)
2. Session fork / continue
3. Advanced search (across all sessions)
4. Summaries / anchors for long sessions
5. Import/export sessions
6. Diagnostics panel
7. Refined animations and transitions
8. Performance optimization (large sessions)
9. Error recovery and edge cases
10. macOS integration (Dock badge, notifications)

**Exit criteria:** Feels like a real product, not a dev tool.

---

## 10. Risk Matrix

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| PTY output parser breaks on Claude Code update | Degraded text display | Medium | File watcher provides fallback authoritative data |
| Hooks API changes | Lost tool events | Low | Hooks are official, documented API |
| Claude session file format changes | History sync breaks | Medium | File watcher is bonus source, not required for core |
| xterm.js rendering issues in Tauri | Terminal glitches | Low | xterm.js is battle-tested in Tauri |
| Large sessions slow down transcript | Laggy UI | Medium | @tanstack/virtual provides virtualization |
| Codex --json format changes | Broken Codex output | Low | OpenAI documents this format |
| Python sidecar startup slow | Delayed first interaction | Low | Pre-warm sidecar on app launch |

---

## 11. Acceptance Criteria

The project is done when:

1. ✅ Opens as a native macOS app (~25MB, not Electron)
2. ✅ 95% visual match to Codex Desktop (validated by screenshots)
3. ✅ Sidebar with projects and session list
4. ✅ Beautiful chat transcript (not terminal) with markdown, code, tool cards
5. ✅ Claude works without `-p` flag, subscription billing only
6. ✅ Codex integration with account rotation (15 accounts)
7. ✅ Gemini integration for brainstorming
8. ✅ Critic mode: Claude writes, Codex reviews
9. ✅ Embedded terminal drawer
10. ✅ Diff/review panel
11. ✅ Full session history without compaction
12. ✅ Session resume after app restart
13. ✅ Project-aware search
14. ✅ Keyboard-first workflow
15. ✅ Daily-driver quality (no random crashes, no data loss)

---

## 12. Appendix A: Codex CLI Integration Details

### Codex headless mode

```bash
codex exec --json --full-auto -p "prompt here"
```

Output: JSONL stream on stdout. Events include:
- `{"type": "message", "role": "assistant", "content": "..."}`
- `{"type": "tool_call", "name": "file_edit", ...}`
- `{"type": "tool_result", ...}`

### Codex App Server (alternative path)

OpenAI documents Codex App Server as an open-source local server for rich client integration. If we want deeper Codex integration later, we can use it via HTTP instead of CLI.

## 13. Appendix B: File Paths

| What | Where |
|------|-------|
| Triad project | `/Users/martin/triad/` |
| Desktop frontend | `/Users/martin/triad/desktop/` |
| Python backend | `/Users/martin/triad/triad/desktop/` |
| Design tokens | `/Users/martin/triad/docs/design-tokens.json` |
| Design system | `/Users/martin/triad/docs/DESIGN_SYSTEM.md` |
| Screenshots | `/Users/martin/triad/docs/design-references/` |
| Codex CSS source | `/Users/martin/codex-fork/source/webview/assets/index-CrdGJg1L.css` |
| Triad config | `~/.triad/config.yaml` |
| Claude hooks | `~/.claude/settings.json` |
| Event ledger DB | `~/.triad/triad.db` |
| Hook socket | `/tmp/triad-hooks.sock` |
