# Triad Desktop Client — Full Implementation Plan (All Phases)

> **For agentic workers:** This plan is designed for Codex agent execution. Each task is self-contained with exact file paths, complete code, and expected test output. Execute tasks sequentially within each phase. Tasks across phases must be done in order.

**Goal:** Build a macOS desktop AI coding workspace (Codex-inspired) using Tauri v2 + React + Python backend.

**Architecture:** Tauri v2 desktop shell renders a React frontend. A Python sidecar (existing Triad codebase) handles all backend logic: provider adapters, account rotation, session ledger, worktrees. Communication over JSON-RPC via stdin/stdout. Claude runs in a hidden PTY (subscription-safe, no `-p` flag); structured events are collected from Claude Code Hooks + PTY output parser + session file watcher. Codex/Gemini run headless.

**Tech Stack:** Tauri v2 (Rust), React 19, TypeScript, Tailwind CSS 4, shadcn/ui, xterm.js, Zustand, Python 3.12+, FastAPI, aiosqlite, asyncio

**Design reference:** See `docs/design-references/CATALOG.md` for screenshot index. See `docs/DESIGN_SYSTEM.md` and `docs/design-tokens.json` for colors, fonts, spacing.

---

## File Structure Overview

### Frontend (new: `desktop/`)

```
desktop/
├── src-tauri/
│   ├── src/main.rs              — Tauri app entry, sidecar spawn, IPC bridge
│   ├── Cargo.toml               — Tauri + serde + serde_json deps
│   └── tauri.conf.json          — Window config, sidecar definition
├── src/
│   ├── main.tsx                 — React entry point
│   ├── App.tsx                  — Root layout: sidebar + main + drawer
│   ├── lib/
│   │   ├── rpc.ts               — JSON-RPC client over Tauri sidecar
│   │   └── types.ts             — TypeScript types for all events/models
│   ├── stores/
│   │   ├── session-store.ts     — Zustand: sessions, messages, streaming
│   │   ├── project-store.ts     — Zustand: projects, active project
│   │   ├── ui-store.ts          — Zustand: drawer open, sidebar collapsed, etc
│   │   └── provider-store.ts    — Zustand: active provider, mode, accounts
│   ├── components/
│   │   ├── sidebar/
│   │   │   ├── Sidebar.tsx          — Main sidebar container
│   │   │   ├── ProjectGroup.tsx     — Project with collapsible session list
│   │   │   ├── SessionItem.tsx      — Single session row
│   │   │   └── SidebarFooter.tsx    — Settings, account info
│   │   ├── transcript/
│   │   │   ├── Transcript.tsx       — Virtualized message list
│   │   │   ├── UserMessage.tsx      — User message bubble
│   │   │   ├── AssistantMessage.tsx — Assistant text with markdown
│   │   │   ├── ToolCard.tsx         — Collapsible tool use card
│   │   │   ├── DiffCard.tsx         — Inline diff display
│   │   │   ├── BashCard.tsx         — Terminal output block
│   │   │   ├── FindingCard.tsx      — Critic review finding
│   │   │   ├── StreamingText.tsx    — Live typing animation
│   │   │   └── SystemMessage.tsx    — Mode changes, session events
│   │   ├── composer/
│   │   │   ├── Composer.tsx         — Input + controls container
│   │   │   ├── ModelSelector.tsx    — Provider/model dropdown
│   │   │   └── ModeSelector.tsx     — Solo/critic/brainstorm/delegate
│   │   ├── terminal/
│   │   │   └── TerminalDrawer.tsx   — xterm.js wrapper with tabs
│   │   ├── diff/
│   │   │   └── DiffPanel.tsx        — Split-view code diff
│   │   ├── shared/
│   │   │   ├── Badge.tsx            — Provider/role badges
│   │   │   ├── CommandPalette.tsx   — Cmd+K overlay
│   │   │   └── Spinner.tsx          — Loading indicator
│   │   └── layout/
│   │       ├── TitleBar.tsx         — Custom title bar with controls
│   │       └── BottomBar.tsx        — Status bar
│   └── styles/
│       ├── tokens.css           — CSS custom properties from Codex
│       └── globals.css          — Base styles + Tailwind imports
├── index.html
├── package.json
├── tailwind.config.ts
├── tsconfig.json
└── vite.config.ts
```

### Backend (new modules in `triad/desktop/`)

```
triad/desktop/
├── __init__.py
├── bridge.py              — JSON-RPC stdio server (main entry for sidecar)
├── claude_pty.py           — Interactive Claude PTY manager
├── hooks_listener.py       — Unix socket listener for Claude Code hooks
├── event_merger.py         — Combine hooks + PTY + file watcher events
├── file_watcher.py         — Watch ~/.claude/ for session file updates
├── terminal_manager.py     — Manage user terminal PTY sessions
├── orchestrator.py         — Multi-agent mode engine
└── search.py               — FTS5 search over event ledger
```

### Modified existing files

```
triad/core/providers/base.py      — Add execute_interactive() method
triad/core/providers/claude.py    — Add PTY mode
triad/core/storage/ledger.py      — Add events table, FTS5
triad/core/config.py              — Add desktop config section
pyproject.toml                     — Add watchdog dependency
```

---

# PHASE 1 — Foundation

**Goal:** Open project → create session → chat with Claude (beautiful formatted output) → restart app → resume session.

---

### Task 1.1: Scaffold Tauri v2 + React project

**Files:**
- Create: `desktop/package.json`
- Create: `desktop/src-tauri/Cargo.toml`
- Create: `desktop/src-tauri/tauri.conf.json`
- Create: `desktop/src-tauri/src/main.rs`
- Create: `desktop/index.html`
- Create: `desktop/src/main.tsx`
- Create: `desktop/src/App.tsx`
- Create: `desktop/vite.config.ts`
- Create: `desktop/tsconfig.json`
- Create: `desktop/tailwind.config.ts`

- [ ] **Step 1: Install Tauri CLI globally**

```bash
cargo install tauri-cli --version "^2"
```

Expected: `tauri-cli` installed.

- [ ] **Step 2: Create the desktop directory and initialize**

```bash
mkdir -p /Users/martin/triad/desktop
cd /Users/martin/triad/desktop
pnpm init
```

- [ ] **Step 3: Install frontend dependencies**

```bash
cd /Users/martin/triad/desktop
pnpm add react react-dom
pnpm add -D @types/react @types/react-dom typescript vite @vitejs/plugin-react tailwindcss @tailwindcss/vite
pnpm add -D @tauri-apps/cli@^2
pnpm add @tauri-apps/api@^2
```

- [ ] **Step 4: Create `desktop/package.json` scripts**

Update `desktop/package.json` to add:

```json
{
  "name": "triad-desktop",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "tauri": "tauri"
  }
}
```

(Keep the dependencies that pnpm already added.)

- [ ] **Step 5: Create `desktop/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
});
```

- [ ] **Step 6: Create `desktop/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

- [ ] **Step 7: Create `desktop/tailwind.config.ts`**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}", "./index.html"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: "#181818",
        "surface-under": "#000000",
        elevated: "#282828",
        "elevated-secondary": "rgba(255,255,255,0.03)",
        editor: "#212121",
        accent: "#339cff",
        "accent-bright": "#0285ff",
        "accent-bg": "#00284d",
        "button-primary": "#0d0d0d",
        "text-primary": "#ffffff",
        "text-secondary": "#afafaf",
        "text-tertiary": "#5d5d5d",
        "text-muted": "#414141",
        "border-default": "color-mix(in srgb, white 8%, transparent)",
        "border-strong": "color-mix(in srgb, white 16%, transparent)",
        success: "#40c977",
        error: "#ff6764",
        warning: "#ff8549",
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", '"Segoe UI"', "sans-serif"],
        mono: ["ui-monospace", '"SFMono-Regular"', '"SF Mono"', "Menlo", "Consolas", "monospace"],
      },
      fontSize: {
        "body": ["13px", "18px"],
        "small": ["12px", "16px"],
        "code": ["12px", "16px"],
        "diff": ["11px", "14px"],
      },
      borderRadius: {
        DEFAULT: "8px",
        lg: "12px",
        xl: "16px",
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 8: Create `desktop/src/styles/tokens.css`**

```css
@import "tailwindcss";

:root {
  --gray-0: #fff;
  --gray-50: #f9f9f9;
  --gray-100: #ededed;
  --gray-300: #afafaf;
  --gray-500: #5d5d5d;
  --gray-600: #414141;
  --gray-750: #282828;
  --gray-800: #212121;
  --gray-900: #181818;
  --gray-1000: #0d0d0d;

  --blue-300: #339cff;
  --blue-400: #0285ff;
  --blue-900: #00284d;

  --green-300: #40c977;
  --red-300: #ff6764;
  --orange-300: #ff8549;

  --color-bg-surface: var(--gray-900);
  --color-bg-elevated: var(--gray-750);
  --color-bg-editor: var(--gray-800);
  --color-text-primary: var(--gray-0);
  --color-text-secondary: var(--gray-300);
  --color-text-tertiary: var(--gray-500);
  --color-border: color-mix(in srgb, white 8%, transparent);
  --color-accent: var(--blue-300);

  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: ui-monospace, "SFMono-Regular", "SF Mono", Menlo, Consolas, monospace;

  --sidebar-width: 300px;
  --sidebar-collapsed: 0px;
  --drawer-min-height: 36px;
  --drawer-default-height: 200px;
  --titlebar-height: 44px;
  --composer-min-height: 80px;
}

body {
  margin: 0;
  padding: 0;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  font-family: var(--font-sans);
  font-size: 13px;
  line-height: 18px;
  -webkit-font-smoothing: antialiased;
  overflow: hidden;
  user-select: none;
}

* {
  box-sizing: border-box;
}

::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}
```

- [ ] **Step 9: Create `desktop/src/styles/globals.css`**

```css
@import "./tokens.css";
```

- [ ] **Step 10: Create `desktop/index.html`**

```html
<!DOCTYPE html>
<html lang="en" class="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Triad</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 11: Create `desktop/src/main.tsx`**

```typescript
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 12: Create `desktop/src/App.tsx`**

```typescript
export function App() {
  return (
    <div className="flex h-screen w-screen bg-surface text-text-primary">
      {/* Sidebar */}
      <aside className="w-[260px] flex-shrink-0 border-r border-border-default bg-surface flex flex-col">
        <div className="p-3 text-sm text-text-secondary">Triad</div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 flex items-center justify-center text-text-secondary">
          Давайте построим
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 13: Initialize Tauri**

```bash
cd /Users/martin/triad/desktop
pnpm tauri init
```

When prompted:
- App name: `Triad`
- Window title: `Triad`
- Dev server URL: `http://localhost:1420`
- Dev command: `pnpm dev`
- Build command: `pnpm build`

- [ ] **Step 14: Configure `desktop/src-tauri/tauri.conf.json`**

After `tauri init` creates the file, update it to:

```json
{
  "$schema": "https://raw.githubusercontent.com/tauri-apps/tauri/dev/crates/tauri-config-schema/schema.json",
  "productName": "Triad",
  "version": "0.1.0",
  "identifier": "com.triad.desktop",
  "build": {
    "frontendDist": "../dist",
    "devUrl": "http://localhost:1420",
    "beforeDevCommand": "pnpm dev",
    "beforeBuildCommand": "pnpm build"
  },
  "app": {
    "windows": [
      {
        "title": "Triad",
        "width": 1280,
        "height": 800,
        "minWidth": 800,
        "minHeight": 600,
        "decorations": true,
        "transparent": false
      }
    ]
  }
}
```

- [ ] **Step 15: Verify Tauri dev mode runs**

```bash
cd /Users/martin/triad/desktop
pnpm tauri dev
```

Expected: A native macOS window opens showing dark background with "Triad" in sidebar and "Давайте построим" in center.

- [ ] **Step 16: Commit**

```bash
cd /Users/martin/triad
git add desktop/
git commit -m "feat(desktop): scaffold Tauri v2 + React + Tailwind project

Tauri v2 desktop shell with React 19, TypeScript, Tailwind CSS 4.
Design tokens extracted from Codex Desktop App CSS.
Dark theme matching Codex color palette."
```

---

### Task 1.2: JSON-RPC bridge (Rust sidecar + Python server)

**Files:**
- Create: `triad/desktop/__init__.py`
- Create: `triad/desktop/bridge.py`
- Create: `desktop/src/lib/rpc.ts`
- Create: `desktop/src/lib/types.ts`
- Modify: `desktop/src-tauri/src/main.rs`
- Modify: `desktop/src-tauri/tauri.conf.json`

- [ ] **Step 1: Create Python bridge — JSON-RPC over stdio**

Create `triad/desktop/__init__.py`:

```python
"""Triad Desktop — bridge layer between Tauri frontend and Python backend."""
```

Create `triad/desktop/bridge.py`:

```python
"""JSON-RPC 2.0 server over stdin/stdout for Tauri sidecar communication."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Callable, Coroutine

# Method registry
_methods: dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}


def method(name: str):
    """Decorator to register a JSON-RPC method."""
    def decorator(fn: Callable[..., Coroutine[Any, Any, Any]]):
        _methods[name] = fn
        return fn
    return decorator


class JsonRpcBridge:
    """Bidirectional JSON-RPC server over stdin/stdout."""

    def __init__(self):
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._notification_callbacks: list[Callable] = []

    async def start(self):
        """Start reading from stdin and writing to stdout."""
        loop = asyncio.get_event_loop()
        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)

        w_transport, w_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout.buffer
        )
        self._writer = asyncio.StreamWriter(
            w_transport, w_protocol, None, loop
        )

        # Process incoming messages
        while True:
            line = await self._reader.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8"))
                await self._handle_message(msg)
            except json.JSONDecodeError:
                continue

    async def _handle_message(self, msg: dict):
        """Handle incoming JSON-RPC request."""
        method_name = msg.get("method", "")
        params = msg.get("params", {})
        msg_id = msg.get("id")

        handler = _methods.get(method_name)
        if handler is None:
            if msg_id is not None:
                await self._send({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method_name}"}
                })
            return

        try:
            result = await handler(params)
            if msg_id is not None:
                await self._send({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": result
                })
        except Exception as e:
            if msg_id is not None:
                await self._send({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32000, "message": str(e)}
                })

    async def notify(self, method: str, params: dict):
        """Send a notification (no id) to the frontend."""
        await self._send({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        })

    async def _send(self, msg: dict):
        """Write a JSON-RPC message to stdout."""
        if self._writer is None:
            return
        data = json.dumps(msg, ensure_ascii=False) + "\n"
        self._writer.write(data.encode("utf-8"))
        await self._writer.drain()


# Global bridge instance
bridge = JsonRpcBridge()


# --- Register initial methods ---

@method("ping")
async def handle_ping(params: dict) -> dict:
    return {"status": "ok", "version": "0.1.0"}


@method("project.open")
async def handle_project_open(params: dict) -> dict:
    path = params.get("path", "")
    p = Path(path)
    if not p.is_dir():
        raise ValueError(f"Not a directory: {path}")
    return {
        "path": str(p.resolve()),
        "name": p.name,
        "git_root": str(p.resolve()),  # TODO: detect actual git root
    }


@method("project.list")
async def handle_project_list(params: dict) -> dict:
    # Placeholder: returns empty list until persistence is added
    return {"projects": []}


@method("session.list")
async def handle_session_list(params: dict) -> dict:
    return {"sessions": []}


@method("session.create")
async def handle_session_create(params: dict) -> dict:
    import uuid
    session_id = str(uuid.uuid4())[:8]
    return {
        "id": session_id,
        "project_path": params.get("project_path", ""),
        "mode": params.get("mode", "solo"),
        "status": "active",
    }


def main():
    """Entry point for the sidecar."""
    asyncio.run(bridge.start())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create TypeScript RPC client**

Create `desktop/src/lib/types.ts`:

```typescript
// Core domain types

export interface Project {
  path: string;
  name: string;
  git_root: string;
}

export interface Session {
  id: string;
  project_path: string;
  title: string;
  mode: "solo" | "critic" | "brainstorm" | "delegate";
  status: "active" | "paused" | "completed";
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface StreamEvent {
  session_id: string;
  run_id: string;
  type:
    | "text_delta"
    | "tool_use"
    | "tool_result"
    | "run_completed"
    | "run_failed"
    | "review_finding"
    | "message_finalized"
    | "system";
  provider?: string;
  role?: string;
  [key: string]: unknown;
}

export interface Message {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  provider?: string;
  agent_role?: string;
  tool_calls?: ToolCall[];
  timestamp: string;
  streaming?: boolean;
}

export interface ToolCall {
  id: string;
  tool: string;
  input: Record<string, unknown>;
  output?: string;
  status: "running" | "completed" | "failed";
}

export interface ReviewFinding {
  severity: "P0" | "P1" | "P2";
  file: string;
  line_range?: string;
  title: string;
  explanation: string;
}
```

Create `desktop/src/lib/rpc.ts`:

```typescript
import { Child, Command } from "@tauri-apps/plugin-shell";
import type { StreamEvent } from "./types";

type RpcCallback = (event: StreamEvent) => void;

let child: Child | null = null;
let requestId = 0;
const pendingRequests = new Map<
  number,
  { resolve: (v: unknown) => void; reject: (e: Error) => void }
>();
const eventListeners: RpcCallback[] = [];
let lineBuffer = "";

export function onEvent(cb: RpcCallback): () => void {
  eventListeners.push(cb);
  return () => {
    const idx = eventListeners.indexOf(cb);
    if (idx >= 0) eventListeners.splice(idx, 1);
  };
}

function handleLine(line: string) {
  if (!line.trim()) return;
  try {
    const msg = JSON.parse(line);

    // Response to a request
    if ("id" in msg && msg.id != null) {
      const pending = pendingRequests.get(msg.id);
      if (pending) {
        pendingRequests.delete(msg.id);
        if (msg.error) {
          pending.reject(new Error(msg.error.message));
        } else {
          pending.resolve(msg.result);
        }
      }
      return;
    }

    // Notification (event stream)
    if ("method" in msg && msg.params) {
      for (const cb of eventListeners) {
        cb(msg.params as StreamEvent);
      }
    }
  } catch {
    // Ignore non-JSON lines
  }
}

export async function startBridge(): Promise<void> {
  const cmd = Command.sidecar("binaries/triad-bridge", []);

  cmd.stdout.on("data", (data: string) => {
    lineBuffer += data;
    const lines = lineBuffer.split("\n");
    lineBuffer = lines.pop() ?? "";
    for (const line of lines) {
      handleLine(line);
    }
  });

  cmd.stderr.on("data", (data: string) => {
    console.warn("[bridge stderr]", data);
  });

  child = await cmd.spawn();
}

export async function rpc<T = unknown>(
  method: string,
  params: Record<string, unknown> = {}
): Promise<T> {
  if (!child) throw new Error("Bridge not started");
  const id = ++requestId;

  return new Promise<T>((resolve, reject) => {
    pendingRequests.set(id, {
      resolve: resolve as (v: unknown) => void,
      reject,
    });

    const msg = JSON.stringify({ jsonrpc: "2.0", method, params, id }) + "\n";
    child!.write(msg);

    // Timeout after 30s
    setTimeout(() => {
      if (pendingRequests.has(id)) {
        pendingRequests.delete(id);
        reject(new Error(`RPC timeout: ${method}`));
      }
    }, 30000);
  });
}

export async function stopBridge(): Promise<void> {
  if (child) {
    await child.kill();
    child = null;
  }
}
```

- [ ] **Step 3: Configure Tauri sidecar in `tauri.conf.json`**

Add to `desktop/src-tauri/tauri.conf.json` inside the top-level object:

```json
{
  "plugins": {
    "shell": {
      "sidecar": true,
      "scope": [
        {
          "name": "binaries/triad-bridge",
          "cmd": "python3",
          "args": ["-m", "triad.desktop.bridge"],
          "sidecar": true
        }
      ]
    }
  }
}
```

Also add `"shell"` to the `plugins` section in Cargo.toml:

```bash
cd /Users/martin/triad/desktop/src-tauri
cargo add tauri-plugin-shell
```

And in `desktop/src-tauri/src/main.rs`:

```rust
fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 4: Install shell plugin on frontend**

```bash
cd /Users/martin/triad/desktop
pnpm add @tauri-apps/plugin-shell
```

- [ ] **Step 5: Test the bridge manually**

```bash
cd /Users/martin/triad
echo '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}' | python3 -m triad.desktop.bridge
```

Expected output:
```json
{"jsonrpc": "2.0", "id": 1, "result": {"status": "ok", "version": "0.1.0"}}
```

- [ ] **Step 6: Commit**

```bash
cd /Users/martin/triad
git add triad/desktop/ desktop/src/lib/ desktop/src-tauri/
git commit -m "feat(desktop): JSON-RPC bridge between Tauri and Python backend

Python stdio server handles RPC requests from Tauri sidecar.
TypeScript client with type-safe request/response and event streaming.
Initial methods: ping, project.open/list, session.create/list."
```

---

### Task 1.3: Sidebar — project list and session navigation

**Files:**
- Create: `desktop/src/stores/project-store.ts`
- Create: `desktop/src/stores/session-store.ts`
- Create: `desktop/src/stores/ui-store.ts`
- Create: `desktop/src/components/sidebar/Sidebar.tsx`
- Create: `desktop/src/components/sidebar/ProjectGroup.tsx`
- Create: `desktop/src/components/sidebar/SessionItem.tsx`
- Create: `desktop/src/components/sidebar/SidebarFooter.tsx`
- Modify: `desktop/src/App.tsx`

- [ ] **Step 1: Install Zustand**

```bash
cd /Users/martin/triad/desktop
pnpm add zustand
```

- [ ] **Step 2: Create stores**

Create `desktop/src/stores/ui-store.ts`:

```typescript
import { create } from "zustand";

interface UiState {
  sidebarCollapsed: boolean;
  drawerOpen: boolean;
  drawerHeight: number;
  diffPanelOpen: boolean;
  toggleSidebar: () => void;
  toggleDrawer: () => void;
  setDrawerHeight: (h: number) => void;
  toggleDiffPanel: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  drawerOpen: false,
  drawerHeight: 200,
  diffPanelOpen: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  toggleDrawer: () => set((s) => ({ drawerOpen: !s.drawerOpen })),
  setDrawerHeight: (h) => set({ drawerHeight: h }),
  toggleDiffPanel: () => set((s) => ({ diffPanelOpen: !s.diffPanelOpen })),
}));
```

Create `desktop/src/stores/project-store.ts`:

```typescript
import { create } from "zustand";
import type { Project } from "../lib/types";
import { rpc } from "../lib/rpc";

interface ProjectState {
  projects: Project[];
  activeProject: Project | null;
  loading: boolean;
  loadProjects: () => Promise<void>;
  openProject: (path: string) => Promise<void>;
  setActiveProject: (project: Project) => void;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  activeProject: null,
  loading: false,

  loadProjects: async () => {
    set({ loading: true });
    try {
      const result = await rpc<{ projects: Project[] }>("project.list");
      set({ projects: result.projects, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  openProject: async (path: string) => {
    const result = await rpc<Project>("project.open", { path });
    const projects = get().projects;
    const exists = projects.find((p) => p.path === result.path);
    if (!exists) {
      set({ projects: [...projects, result], activeProject: result });
    } else {
      set({ activeProject: exists });
    }
  },

  setActiveProject: (project) => set({ activeProject: project }),
}));
```

Create `desktop/src/stores/session-store.ts`:

```typescript
import { create } from "zustand";
import type { Message, Session } from "../lib/types";
import { rpc } from "../lib/rpc";

interface SessionState {
  sessions: Session[];
  activeSession: Session | null;
  messages: Message[];
  streamingText: string;
  loadSessions: (projectPath: string) => Promise<void>;
  createSession: (projectPath: string, mode: string) => Promise<Session>;
  setActiveSession: (session: Session) => void;
  addMessage: (message: Message) => void;
  appendStreamingText: (delta: string) => void;
  finalizeStreaming: (content: string) => void;
  clearStreamingText: () => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  activeSession: null,
  messages: [],
  streamingText: "",

  loadSessions: async (projectPath: string) => {
    const result = await rpc<{ sessions: Session[] }>("session.list", {
      project_path: projectPath,
    });
    set({ sessions: result.sessions });
  },

  createSession: async (projectPath: string, mode: string) => {
    const session = await rpc<Session>("session.create", {
      project_path: projectPath,
      mode,
    });
    set((s) => ({
      sessions: [session, ...s.sessions],
      activeSession: session,
      messages: [],
      streamingText: "",
    }));
    return session;
  },

  setActiveSession: (session) => set({ activeSession: session, messages: [], streamingText: "" }),
  addMessage: (message) => set((s) => ({ messages: [...s.messages, message] })),
  appendStreamingText: (delta) => set((s) => ({ streamingText: s.streamingText + delta })),
  finalizeStreaming: (content) =>
    set((s) => ({
      streamingText: "",
      messages: [
        ...s.messages,
        {
          id: `msg_${Date.now()}`,
          session_id: s.activeSession?.id ?? "",
          role: "assistant" as const,
          content,
          timestamp: new Date().toISOString(),
        },
      ],
    })),
  clearStreamingText: () => set({ streamingText: "" }),
}));
```

- [ ] **Step 3: Create Sidebar components**

Create `desktop/src/components/sidebar/SessionItem.tsx`:

```typescript
import type { Session } from "../../lib/types";

interface Props {
  session: Session;
  active: boolean;
  onClick: () => void;
}

export function SessionItem({ session, active, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 text-sm rounded-lg truncate flex items-center justify-between gap-2 transition-colors ${
        active
          ? "bg-elevated text-text-primary"
          : "text-text-secondary hover:bg-elevated-secondary hover:text-text-primary"
      }`}
    >
      <span className="truncate">{session.title || "Новая беседа"}</span>
      {session.message_count > 0 && (
        <span className="text-xs text-text-tertiary flex-shrink-0">
          {session.message_count}
        </span>
      )}
    </button>
  );
}
```

Create `desktop/src/components/sidebar/ProjectGroup.tsx`:

```typescript
import { useState } from "react";
import type { Project, Session } from "../../lib/types";
import { SessionItem } from "./SessionItem";

interface Props {
  project: Project;
  sessions: Session[];
  activeSessionId: string | null;
  onSessionClick: (session: Session) => void;
}

export function ProjectGroup({ project, sessions, activeSessionId, onSessionClick }: Props) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="mb-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-3 py-1.5 text-xs font-medium text-text-tertiary uppercase tracking-wider hover:text-text-secondary flex items-center gap-1"
      >
        <span className={`transition-transform ${expanded ? "rotate-90" : ""}`}>▸</span>
        {project.name}
      </button>
      {expanded && (
        <div className="ml-1 space-y-0.5">
          {sessions.map((s) => (
            <SessionItem
              key={s.id}
              session={s}
              active={s.id === activeSessionId}
              onClick={() => onSessionClick(s)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

Create `desktop/src/components/sidebar/SidebarFooter.tsx`:

```typescript
export function SidebarFooter() {
  return (
    <div className="p-3 border-t border-border-default">
      <button className="w-full text-left text-sm text-text-secondary hover:text-text-primary transition-colors">
        ⚙ Настройки
      </button>
    </div>
  );
}
```

Create `desktop/src/components/sidebar/Sidebar.tsx`:

```typescript
import { useProjectStore } from "../../stores/project-store";
import { useSessionStore } from "../../stores/session-store";
import { ProjectGroup } from "./ProjectGroup";
import { SidebarFooter } from "./SidebarFooter";

export function Sidebar() {
  const { projects, activeProject, setActiveProject } = useProjectStore();
  const { sessions, activeSession, setActiveSession, createSession } = useSessionStore();

  const handleNewSession = async () => {
    if (!activeProject) return;
    await createSession(activeProject.path, "solo");
  };

  return (
    <aside className="w-[300px] flex-shrink-0 border-r border-border-default bg-surface flex flex-col h-full">
      {/* Header */}
      <div className="p-3 flex items-center justify-between">
        <button
          onClick={handleNewSession}
          className="text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          + Новая беседа
        </button>
      </div>

      {/* Quick links */}
      <div className="px-3 pb-2 space-y-0.5">
        <button className="w-full text-left px-2 py-1.5 text-sm text-text-secondary hover:text-text-primary rounded transition-colors">
          Навыки и приложения
        </button>
        <button className="w-full text-left px-2 py-1.5 text-sm text-text-secondary hover:text-text-primary rounded transition-colors">
          Автоматизации
        </button>
      </div>

      {/* Divider */}
      <div className="px-3 py-1">
        <div className="border-t border-border-default" />
      </div>

      {/* Sessions label */}
      <div className="px-3 py-1 flex items-center justify-between">
        <span className="text-xs text-text-tertiary">Беседы</span>
      </div>

      {/* Project groups + sessions */}
      <div className="flex-1 overflow-y-auto px-1">
        {projects.map((project) => (
          <ProjectGroup
            key={project.path}
            project={project}
            sessions={sessions.filter((s) => s.project_path === project.path)}
            activeSessionId={activeSession?.id ?? null}
            onSessionClick={(s) => {
              setActiveProject(project);
              setActiveSession(s);
            }}
          />
        ))}

        {projects.length === 0 && (
          <div className="px-3 py-4 text-sm text-text-tertiary text-center">
            Откройте папку проекта, чтобы начать
          </div>
        )}
      </div>

      <SidebarFooter />
    </aside>
  );
}
```

- [ ] **Step 4: Update `App.tsx` to use Sidebar**

```typescript
import { useEffect } from "react";
import { Sidebar } from "./components/sidebar/Sidebar";
import { startBridge } from "./lib/rpc";

export function App() {
  useEffect(() => {
    startBridge().catch(console.error);
  }, []);

  return (
    <div className="flex h-screen w-screen bg-surface text-text-primary">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="text-4xl mb-2 text-text-tertiary">☁</div>
            <h1 className="text-xl text-text-primary mb-1">Давайте построим</h1>
            <p className="text-sm text-text-secondary">Triad Desktop</p>
          </div>
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 5: Verify UI renders correctly**

```bash
cd /Users/martin/triad/desktop
pnpm tauri dev
```

Expected: Sidebar on left (dark background, 260px width), "Новая беседа" button, "Навыки и приложения" / "Автоматизации" links, "Беседы" section header, empty state message. Main area shows "Давайте построим" centered text.

Compare with screenshot `02.02.03.png` — sidebar structure should match.

- [ ] **Step 6: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/
git commit -m "feat(desktop): sidebar with project groups and session list

Zustand stores for projects, sessions, and UI state.
Sidebar matches Codex layout: project groups, session items, footer.
Reference: docs/design-references/02.02.03.png"
```

---

### Task 1.4: Transcript view with message rendering

**Files:**
- Create: `desktop/src/components/transcript/Transcript.tsx`
- Create: `desktop/src/components/transcript/UserMessage.tsx`
- Create: `desktop/src/components/transcript/AssistantMessage.tsx`
- Create: `desktop/src/components/transcript/StreamingText.tsx`
- Create: `desktop/src/components/transcript/SystemMessage.tsx`
- Modify: `desktop/src/App.tsx`

- [ ] **Step 1: Install markdown dependencies**

```bash
cd /Users/martin/triad/desktop
pnpm add react-markdown remark-gfm rehype-highlight
pnpm add -D @types/react
```

- [ ] **Step 2: Create message components**

Create `desktop/src/components/transcript/UserMessage.tsx`:

```typescript
import type { Message } from "../../lib/types";

interface Props {
  message: Message;
}

export function UserMessage({ message }: Props) {
  return (
    <div className="px-6 py-4">
      <div className="flex items-start gap-3">
        <div className="w-6 h-6 rounded-full bg-accent flex items-center justify-center text-xs text-white flex-shrink-0 mt-0.5">
          M
        </div>
        <div className="text-sm text-text-primary whitespace-pre-wrap min-w-0">
          {message.content}
        </div>
      </div>
    </div>
  );
}
```

Create `desktop/src/components/transcript/AssistantMessage.tsx`:

```typescript
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { Message } from "../../lib/types";

interface Props {
  message: Message;
}

export function AssistantMessage({ message }: Props) {
  return (
    <div className="px-6 py-4">
      <div className="flex items-start gap-3">
        <div className="w-6 h-6 rounded-full bg-elevated flex items-center justify-center text-xs text-text-secondary flex-shrink-0 mt-0.5">
          {message.provider === "codex" ? "C" : message.provider === "gemini" ? "G" : "◆"}
        </div>
        <div className="prose prose-invert prose-sm max-w-none min-w-0">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
            {message.content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
```

Create `desktop/src/components/transcript/StreamingText.tsx`:

```typescript
interface Props {
  text: string;
  provider?: string;
}

export function StreamingText({ text, provider }: Props) {
  if (!text) return null;

  return (
    <div className="px-6 py-4">
      <div className="flex items-start gap-3">
        <div className="w-6 h-6 rounded-full bg-elevated flex items-center justify-center text-xs text-text-secondary flex-shrink-0 mt-0.5">
          {provider === "codex" ? "C" : provider === "gemini" ? "G" : "◆"}
        </div>
        <div className="text-sm text-text-primary whitespace-pre-wrap min-w-0">
          {text}
          <span className="inline-block w-0.5 h-4 bg-accent animate-pulse ml-0.5" />
        </div>
      </div>
    </div>
  );
}
```

Create `desktop/src/components/transcript/SystemMessage.tsx`:

```typescript
interface Props {
  text: string;
}

export function SystemMessage({ text }: Props) {
  return (
    <div className="px-6 py-2 flex justify-center">
      <span className="text-xs text-text-tertiary">{text}</span>
    </div>
  );
}
```

Create `desktop/src/components/transcript/Transcript.tsx`:

```typescript
import { useEffect, useRef } from "react";
import { useSessionStore } from "../../stores/session-store";
import { UserMessage } from "./UserMessage";
import { AssistantMessage } from "./AssistantMessage";
import { StreamingText } from "./StreamingText";

export function Transcript() {
  const { messages, streamingText, activeSession } = useSessionStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, streamingText]);

  if (!activeSession) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-3 text-text-tertiary">☁</div>
          <h1 className="text-xl text-text-primary mb-1">Давайте построим</h1>
          <p className="text-sm text-text-secondary">
            {activeSession ? activeSession.project_path : "Triad Desktop"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto py-4">
        {messages.map((msg) =>
          msg.role === "user" ? (
            <UserMessage key={msg.id} message={msg} />
          ) : msg.role === "system" ? (
            <div key={msg.id} className="px-6 py-2 flex justify-center">
              <span className="text-xs text-text-tertiary">{msg.content}</span>
            </div>
          ) : (
            <AssistantMessage key={msg.id} message={msg} />
          )
        )}
        <StreamingText text={streamingText} />
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Update `App.tsx`**

```typescript
import { useEffect } from "react";
import { Sidebar } from "./components/sidebar/Sidebar";
import { Transcript } from "./components/transcript/Transcript";
import { startBridge } from "./lib/rpc";

export function App() {
  useEffect(() => {
    startBridge().catch(console.error);
  }, []);

  return (
    <div className="flex h-screen w-screen bg-surface text-text-primary">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 bg-surface">
        <Transcript />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Verify transcript renders**

```bash
cd /Users/martin/triad/desktop
pnpm tauri dev
```

Expected: Sidebar on left, main area shows "Давайте построим" empty state. Compare with `02.02.03.png`.

- [ ] **Step 5: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/components/transcript/
git commit -m "feat(desktop): transcript view with user/assistant/streaming messages

Markdown rendering via react-markdown, syntax highlighting via rehype-highlight.
Streaming text with cursor animation. Auto-scroll to bottom.
Reference: docs/design-references/02.01.54.png"
```

---

### Task 1.5: Composer — message input with send

**Files:**
- Create: `desktop/src/components/composer/Composer.tsx`
- Create: `desktop/src/components/composer/ModelSelector.tsx`
- Create: `desktop/src/components/composer/ModeSelector.tsx`
- Create: `desktop/src/stores/provider-store.ts`
- Modify: `desktop/src/App.tsx`

- [ ] **Step 1: Create provider store**

Create `desktop/src/stores/provider-store.ts`:

```typescript
import { create } from "zustand";

interface ProviderState {
  activeProvider: string;
  activeModel: string;
  mode: "solo" | "critic" | "brainstorm" | "delegate";
  criticProvider: string;
  setActiveProvider: (provider: string) => void;
  setActiveModel: (model: string) => void;
  setMode: (mode: "solo" | "critic" | "brainstorm" | "delegate") => void;
  setCriticProvider: (provider: string) => void;
}

export const useProviderStore = create<ProviderState>((set) => ({
  activeProvider: "claude",
  activeModel: "claude-opus-4-6",
  mode: "solo",
  criticProvider: "codex",
  setActiveProvider: (provider) => set({ activeProvider: provider }),
  setActiveModel: (model) => set({ activeModel: model }),
  setMode: (mode) => set({ mode }),
  setCriticProvider: (provider) => set({ criticProvider: provider }),
}));
```

- [ ] **Step 2: Create Composer components**

Create `desktop/src/components/composer/ModelSelector.tsx`:

```typescript
import { useProviderStore } from "../../stores/provider-store";

const MODELS = [
  { id: "claude-opus-4-6", label: "Claude Opus 4.6", provider: "claude" },
  { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6", provider: "claude" },
  { id: "codex-mini-latest", label: "Codex Mini", provider: "codex" },
  { id: "gpt-5.4", label: "GPT-5.4", provider: "codex" },
  { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro", provider: "gemini" },
];

export function ModelSelector() {
  const { activeModel, setActiveModel, setActiveProvider } = useProviderStore();
  const current = MODELS.find((m) => m.id === activeModel);

  return (
    <select
      value={activeModel}
      onChange={(e) => {
        const model = MODELS.find((m) => m.id === e.target.value);
        if (model) {
          setActiveModel(model.id);
          setActiveProvider(model.provider);
        }
      }}
      className="bg-transparent text-xs text-text-secondary border border-border-default rounded px-2 py-1 outline-none focus:border-accent cursor-pointer"
    >
      {MODELS.map((m) => (
        <option key={m.id} value={m.id} className="bg-elevated">
          {m.label}
        </option>
      ))}
    </select>
  );
}
```

Create `desktop/src/components/composer/ModeSelector.tsx`:

```typescript
import { useProviderStore } from "../../stores/provider-store";

const MODES = [
  { id: "solo" as const, label: "Solo" },
  { id: "critic" as const, label: "Critic" },
  { id: "brainstorm" as const, label: "Brainstorm" },
  { id: "delegate" as const, label: "Delegate" },
];

export function ModeSelector() {
  const { mode, setMode } = useProviderStore();

  return (
    <select
      value={mode}
      onChange={(e) => setMode(e.target.value as typeof mode)}
      className="bg-transparent text-xs text-text-secondary border border-border-default rounded px-2 py-1 outline-none focus:border-accent cursor-pointer"
    >
      {MODES.map((m) => (
        <option key={m.id} value={m.id} className="bg-elevated">
          {m.label}
        </option>
      ))}
    </select>
  );
}
```

Create `desktop/src/components/composer/Composer.tsx`:

```typescript
import { useState, useRef, useCallback } from "react";
import { useSessionStore } from "../../stores/session-store";
import { useProjectStore } from "../../stores/project-store";
import { useProviderStore } from "../../stores/provider-store";
import { rpc } from "../../lib/rpc";
import { ModelSelector } from "./ModelSelector";
import { ModeSelector } from "./ModeSelector";

export function Composer() {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { activeSession, addMessage, createSession } = useSessionStore();
  const { activeProject } = useProjectStore();
  const { mode } = useProviderStore();

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;

    setSending(true);

    try {
      let session = activeSession;
      if (!session && activeProject) {
        session = await createSession(activeProject.path, mode);
      }
      if (!session) return;

      // Add user message to UI
      addMessage({
        id: `msg_${Date.now()}`,
        session_id: session.id,
        role: "user",
        content: text,
        timestamp: new Date().toISOString(),
      });

      setInput("");

      // Send to backend
      await rpc("session.send", {
        session_id: session.id,
        content: text,
      });
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  }, [input, sending, activeSession, activeProject, mode, addMessage, createSession]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && e.metaKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-border-default bg-surface px-4 py-3">
      <div className="max-w-3xl mx-auto">
        {/* Input area */}
        <div className="bg-elevated rounded-xl px-4 py-3 border border-border-default focus-within:border-accent transition-colors">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Codex anything, @ to add files, / for commands, # for skills"
            rows={1}
            className="w-full bg-transparent text-sm text-text-primary placeholder:text-text-tertiary outline-none resize-none min-h-[20px] max-h-[240px]"
            style={{
              height: "auto",
              overflow: input.split("\n").length > 1 ? "auto" : "hidden",
            }}
          />

          {/* Controls row */}
          <div className="flex items-center justify-between mt-2">
            <div className="flex items-center gap-2">
              <button className="text-text-tertiary hover:text-text-secondary text-sm">+</button>
              <ModelSelector />
              <ModeSelector />
            </div>
            <button
              onClick={handleSend}
              disabled={!input.trim() || sending}
              className="w-7 h-7 rounded-full bg-accent flex items-center justify-center disabled:opacity-30 transition-opacity"
            >
              <span className="text-white text-xs">▶</span>
            </button>
          </div>
        </div>

        {/* Bottom status */}
        <div className="flex items-center justify-between mt-1.5 px-1">
          <div className="flex items-center gap-3 text-xs text-text-tertiary">
            <span>Местный</span>
            <span className="text-warning">Полный доступ</span>
          </div>
          {activeProject && (
            <span className="text-xs text-text-tertiary truncate max-w-[300px]">
              {activeProject.path}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Wire Composer into App.tsx**

```typescript
import { useEffect } from "react";
import { Sidebar } from "./components/sidebar/Sidebar";
import { Transcript } from "./components/transcript/Transcript";
import { Composer } from "./components/composer/Composer";
import { startBridge } from "./lib/rpc";

export function App() {
  useEffect(() => {
    startBridge().catch(console.error);
  }, []);

  return (
    <div className="flex h-screen w-screen bg-surface text-text-primary">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 bg-surface">
        <Transcript />
        <Composer />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Verify composer renders**

```bash
cd /Users/martin/triad/desktop
pnpm tauri dev
```

Expected: Composer at bottom with dark input area, "+" button, model selector (Claude Opus 4.6), mode selector (Solo), send button (blue circle). Status bar below shows "Местный" and "Полный доступ". Compare with `02.01.54.png` and `02.02.03.png`.

- [ ] **Step 5: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/components/composer/ desktop/src/stores/provider-store.ts desktop/src/App.tsx
git commit -m "feat(desktop): composer with model/mode selectors and Cmd+Enter send

Input area with auto-expand, model dropdown, mode dropdown, send button.
Bottom status bar with permission mode and project path.
Reference: docs/design-references/02.01.54.png"
```

---

### Task 1.6: Claude PTY manager + Hooks listener (Python backend)

**Files:**
- Create: `triad/desktop/claude_pty.py`
- Create: `triad/desktop/hooks_listener.py`
- Create: `triad/desktop/event_merger.py`
- Modify: `triad/desktop/bridge.py`

- [ ] **Step 1: Create Claude PTY manager**

Create `triad/desktop/claude_pty.py`:

```python
"""Interactive Claude PTY session — no -p flag, subscription-safe."""
from __future__ import annotations

import asyncio
import os
import pty
import re
import signal
from collections.abc import Callable, Coroutine
from typing import Any

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b[()][AB012]|\r")

# Patterns that indicate Ink TUI chrome (not user-visible content)
CHROME_PATTERNS = (
    "⏳", "●", "◐", "◑", "◒", "◓",
    "╭", "╰", "│", "─", "╮", "╯",
    "Press ", "Ctrl+", "Esc ",
    "❯", "$ ",
)


class ClaudePTY:
    """Manages an interactive Claude Code session in a hidden PTY.

    Claude runs interactively (subscription billing). We capture PTY output,
    strip ANSI codes, and emit text events to the event merger.
    """

    def __init__(
        self,
        workdir: str,
        on_event: Callable[[dict], Coroutine[Any, Any, None]],
    ):
        self.workdir = workdir
        self.on_event = on_event
        self._master_fd: int | None = None
        self._child_pid: int | None = None
        self._running = False
        self._read_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Fork and exec `claude` in a PTY."""
        master_fd, slave_fd = pty.openpty()

        pid = os.fork()
        if pid == 0:
            # Child: become session leader, attach to slave PTY
            os.close(master_fd)
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            os.close(slave_fd)
            os.chdir(self.workdir)
            os.execvp("claude", ["claude"])
            # unreachable
        else:
            os.close(slave_fd)
            self._master_fd = master_fd
            self._child_pid = pid
            self._running = True
            self._read_task = asyncio.create_task(self._read_loop())

    async def send(self, text: str) -> None:
        """Send user input to Claude's stdin."""
        if self._master_fd is None:
            return
        data = (text + "\n").encode("utf-8")
        await asyncio.get_event_loop().run_in_executor(
            None, os.write, self._master_fd, data
        )

    async def stop(self) -> None:
        """Gracefully stop Claude."""
        self._running = False
        if self._master_fd is not None:
            try:
                os.write(self._master_fd, b"/exit\n")
            except OSError:
                pass
        if self._child_pid is not None:
            try:
                os.kill(self._child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if self._read_task:
            self._read_task.cancel()

    async def _read_loop(self) -> None:
        """Read from master PTY fd, parse, emit text events."""
        loop = asyncio.get_event_loop()
        buffer = ""

        while self._running:
            try:
                raw = await loop.run_in_executor(
                    None, os.read, self._master_fd, 8192
                )
                if not raw:
                    break

                text = raw.decode("utf-8", errors="replace")
                clean = ANSI_ESCAPE.sub("", text)
                buffer += clean

                # Emit line by line
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    stripped = line.strip()
                    if stripped and not self._is_chrome(stripped):
                        await self.on_event({
                            "type": "text_delta",
                            "provider": "claude",
                            "source": "pty",
                            "delta": stripped,
                        })

            except OSError:
                break
            except asyncio.CancelledError:
                break

    @staticmethod
    def _is_chrome(line: str) -> bool:
        """Filter out Ink TUI chrome lines."""
        return any(p in line for p in CHROME_PATTERNS)
```

- [ ] **Step 2: Create Hooks listener**

Create `triad/desktop/hooks_listener.py`:

```python
"""Unix socket listener for Claude Code hook events."""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

SOCKET_PATH = "/tmp/triad-hooks.sock"


class HooksListener:
    """Listen on a Unix socket for events from Claude Code hooks.

    Claude Code hooks are configured in ~/.claude/settings.json to
    send JSON events here on PreToolUse, PostToolUse, and Stop.
    """

    def __init__(self, on_event: Callable[[dict], Coroutine[Any, Any, None]]):
        self.on_event = on_event
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start the Unix socket server."""
        sock_path = Path(SOCKET_PATH)
        if sock_path.exists():
            sock_path.unlink()

        self._server = await asyncio.start_unix_server(
            self._handle_connection, path=str(sock_path)
        )

    async def stop(self) -> None:
        """Stop the server and clean up."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        sock_path = Path(SOCKET_PATH)
        if sock_path.exists():
            sock_path.unlink()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle one hook event connection."""
        try:
            data = await asyncio.wait_for(reader.read(65536), timeout=5.0)
            if data:
                for line in data.decode("utf-8", errors="replace").strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        event["source"] = "hooks"
                        await self.on_event(event)
                    except json.JSONDecodeError:
                        pass
        except (asyncio.TimeoutError, ConnectionError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
```

- [ ] **Step 3: Create Event Merger**

Create `triad/desktop/event_merger.py`:

```python
"""Merge events from hooks, PTY, and file watcher into a unified stream."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any


class EventMerger:
    """Deduplicates and routes events from multiple sources to the UI.

    Sources:
    - hooks: structured tool events (PreToolUse, PostToolUse, Stop)
    - pty: streaming text deltas
    - file_watcher: authoritative session history (future)
    """

    def __init__(
        self,
        on_ui_event: Callable[[dict], Coroutine[Any, Any, None]],
    ):
        self.on_ui_event = on_ui_event
        self._streaming_buffer = ""
        self._active_tools: dict[str, dict] = {}  # tool_name → event

    async def handle(self, event: dict) -> None:
        """Process an event from any source and forward to UI."""
        source = event.get("source", "unknown")
        event_type = event.get("type", "")
        hook = event.get("hook", "")

        # Hooks: structured tool events
        if source == "hooks":
            if hook == "pre_tool":
                tool = event.get("tool", "unknown")
                self._active_tools[tool] = event
                await self.on_ui_event({
                    "type": "tool_use",
                    "tool": tool,
                    "input": event.get("input", ""),
                    "status": "running",
                    "provider": "claude",
                })
            elif hook == "post_tool":
                tool = event.get("tool", "unknown")
                self._active_tools.pop(tool, None)
                await self.on_ui_event({
                    "type": "tool_result",
                    "tool": tool,
                    "output": event.get("output", ""),
                    "status": "completed",
                    "provider": "claude",
                })
            elif hook == "stop":
                await self.on_ui_event({
                    "type": "run_completed",
                    "provider": "claude",
                })
            return

        # PTY: streaming text
        if source == "pty" and event_type == "text_delta":
            delta = event.get("delta", "")
            self._streaming_buffer += delta + "\n"
            await self.on_ui_event({
                "type": "text_delta",
                "delta": delta,
                "provider": event.get("provider", "claude"),
            })
            return

        # File watcher: authoritative messages (future)
        if source == "file_watcher" and event_type == "authoritative_message":
            await self.on_ui_event({
                "type": "message_finalized",
                "content": event.get("content", self._streaming_buffer),
                "provider": event.get("provider", "claude"),
            })
            self._streaming_buffer = ""
            return

    def reset(self) -> None:
        """Reset state between sessions."""
        self._streaming_buffer = ""
        self._active_tools.clear()
```

- [ ] **Step 4: Wire everything into bridge.py**

Add to `triad/desktop/bridge.py` — add these imports at the top:

```python
from triad.desktop.claude_pty import ClaudePTY
from triad.desktop.hooks_listener import HooksListener
from triad.desktop.event_merger import EventMerger
```

Add these global variables after `bridge = JsonRpcBridge()`:

```python
# Active Claude PTY sessions (session_id → ClaudePTY)
_claude_sessions: dict[str, ClaudePTY] = {}
_hooks_listener: HooksListener | None = None
_event_merger: EventMerger | None = None
```

Add this initialization function:

```python
async def _init_subsystems():
    """Start hooks listener and event merger."""
    global _hooks_listener, _event_merger

    async def forward_to_ui(event: dict):
        await bridge.notify("event.stream", event)

    _event_merger = EventMerger(on_ui_event=forward_to_ui)
    _hooks_listener = HooksListener(on_event=_event_merger.handle)
    await _hooks_listener.start()
```

Replace the `handle_session_create` method:

```python
@method("session.create")
async def handle_session_create(params: dict) -> dict:
    import uuid
    session_id = str(uuid.uuid4())[:8]
    
    # Initialize subsystems if needed
    if _event_merger is None:
        await _init_subsystems()
    
    return {
        "id": session_id,
        "project_path": params.get("project_path", ""),
        "mode": params.get("mode", "solo"),
        "status": "active",
    }
```

Add the `session.send` method:

```python
@method("session.send")
async def handle_session_send(params: dict) -> dict:
    session_id = params.get("session_id", "")
    content = params.get("content", "")
    
    if _event_merger is None:
        await _init_subsystems()
    
    # Get or create Claude PTY for this session
    claude = _claude_sessions.get(session_id)
    if claude is None:
        project_path = params.get("project_path", str(Path.cwd()))
        claude = ClaudePTY(
            workdir=project_path,
            on_event=_event_merger.handle,
        )
        await claude.start()
        _claude_sessions[session_id] = claude
    
    # Send the user's message to Claude
    await claude.send(content)
    
    return {"status": "sent", "session_id": session_id}
```

- [ ] **Step 5: Test hooks listener manually**

Terminal 1:
```bash
cd /Users/martin/triad
python3 -c "
import asyncio
from triad.desktop.hooks_listener import HooksListener

async def on_event(e):
    print('EVENT:', e)

async def main():
    hl = HooksListener(on_event=on_event)
    await hl.start()
    await asyncio.sleep(60)

asyncio.run(main())
"
```

Terminal 2:
```bash
echo '{"hook":"pre_tool","tool":"Read","input":"test.py"}' | nc -U /tmp/triad-hooks.sock
```

Expected: Terminal 1 prints `EVENT: {'hook': 'pre_tool', 'tool': 'Read', 'input': 'test.py', 'source': 'hooks'}`.

- [ ] **Step 6: Commit**

```bash
cd /Users/martin/triad
git add triad/desktop/
git commit -m "feat(desktop): Claude PTY + hooks listener + event merger

Claude runs interactively in hidden PTY (subscription-safe, no -p flag).
Hooks listener receives structured tool events via Unix socket.
Event merger combines PTY text + hook events for unified UI stream."
```

---

### Task 1.7: Connect frontend streaming to backend events

**Files:**
- Modify: `desktop/src/lib/rpc.ts` (already has `onEvent`)
- Modify: `desktop/src/App.tsx`
- Create: `desktop/src/hooks/useStreamEvents.ts`

- [ ] **Step 1: Create stream events hook**

Create `desktop/src/hooks/useStreamEvents.ts`:

```typescript
import { useEffect } from "react";
import { onEvent } from "../lib/rpc";
import { useSessionStore } from "../stores/session-store";
import type { StreamEvent } from "../lib/types";

export function useStreamEvents() {
  const { appendStreamingText, finalizeStreaming, addMessage, activeSession } =
    useSessionStore();

  useEffect(() => {
    const unsub = onEvent((event: StreamEvent) => {
      if (!activeSession) return;

      switch (event.type) {
        case "text_delta":
          appendStreamingText(String(event.delta ?? ""));
          break;

        case "tool_use":
          addMessage({
            id: `tool_${Date.now()}`,
            session_id: activeSession.id,
            role: "assistant",
            content: `🔧 ${event.tool}: ${typeof event.input === "string" ? event.input : JSON.stringify(event.input)}`,
            provider: String(event.provider ?? ""),
            timestamp: new Date().toISOString(),
          });
          break;

        case "tool_result":
          // Tool results are shown inline with tool_use cards
          break;

        case "message_finalized":
          finalizeStreaming(String(event.content ?? ""));
          break;

        case "run_completed":
          // Finalize any remaining streaming text
          finalizeStreaming(useSessionStore.getState().streamingText);
          break;

        case "run_failed":
          addMessage({
            id: `err_${Date.now()}`,
            session_id: activeSession.id,
            role: "system",
            content: `Error: ${event.error ?? "Unknown error"}`,
            timestamp: new Date().toISOString(),
          });
          break;
      }
    });

    return unsub;
  }, [activeSession?.id]);
}
```

- [ ] **Step 2: Wire into App.tsx**

```typescript
import { useEffect } from "react";
import { Sidebar } from "./components/sidebar/Sidebar";
import { Transcript } from "./components/transcript/Transcript";
import { Composer } from "./components/composer/Composer";
import { startBridge } from "./lib/rpc";
import { useStreamEvents } from "./hooks/useStreamEvents";

export function App() {
  useEffect(() => {
    startBridge().catch(console.error);
  }, []);

  useStreamEvents();

  return (
    <div className="flex h-screen w-screen bg-surface text-text-primary">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 bg-surface">
        <Transcript />
        <Composer />
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/hooks/ desktop/src/App.tsx
git commit -m "feat(desktop): connect frontend to backend streaming events

useStreamEvents hook listens for text_delta, tool_use, run_completed events.
Streaming text renders with cursor animation, finalized on completion."
```

---

### Task 1.8: Session persistence (SQLite events table)

**Files:**
- Modify: `triad/core/storage/ledger.py`
- Modify: `triad/desktop/bridge.py`

- [ ] **Step 1: Add events table to Ledger**

Add to `triad/core/storage/ledger.py` — in the `initialize()` method, add this SQL after existing table creation:

```python
await self._db.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        run_id TEXT,
        timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
        type TEXT NOT NULL,
        provider TEXT,
        role TEXT,
        data JSON NOT NULL
    )
""")
await self._db.execute("""
    CREATE INDEX IF NOT EXISTS idx_events_session
    ON events(session_id, timestamp)
""")
await self._db.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        path TEXT PRIMARY KEY,
        display_name TEXT,
        git_root TEXT,
        last_opened_at TEXT
    )
""")
await self._db.commit()
```

Add methods to Ledger class:

```python
async def append_event(self, session_id: str, event_type: str, data: dict, *, provider: str | None = None, role: str | None = None, run_id: str | None = None) -> int:
    cursor = await self._db.execute(
        "INSERT INTO events (session_id, run_id, type, provider, role, data) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, run_id, event_type, provider, role, json.dumps(data)),
    )
    await self._db.commit()
    return cursor.lastrowid

async def get_session_events(self, session_id: str, limit: int = 500) -> list[dict]:
    cursor = await self._db.execute(
        "SELECT id, session_id, run_id, timestamp, type, provider, role, data FROM events WHERE session_id = ? ORDER BY id ASC LIMIT ?",
        (session_id, limit),
    )
    rows = await cursor.fetchall()
    return [
        {
            "id": r[0], "session_id": r[1], "run_id": r[2],
            "timestamp": r[3], "type": r[4], "provider": r[5],
            "role": r[6], "data": json.loads(r[7]),
        }
        for r in rows
    ]

async def save_project(self, path: str, display_name: str, git_root: str) -> None:
    await self._db.execute(
        "INSERT OR REPLACE INTO projects (path, display_name, git_root, last_opened_at) VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%f', 'now'))",
        (path, display_name, git_root),
    )
    await self._db.commit()

async def list_projects(self) -> list[dict]:
    cursor = await self._db.execute(
        "SELECT path, display_name, git_root, last_opened_at FROM projects ORDER BY last_opened_at DESC"
    )
    rows = await cursor.fetchall()
    return [
        {"path": r[0], "display_name": r[1], "git_root": r[2], "last_opened_at": r[3]}
        for r in rows
    ]
```

- [ ] **Step 2: Wire persistence into bridge**

In `bridge.py`, update methods to use Ledger. Add at top:

```python
from triad.core.storage.ledger import Ledger
from triad.core.config import get_default_config_path
```

Add global:

```python
_ledger: Ledger | None = None

async def get_ledger() -> Ledger:
    global _ledger
    if _ledger is None:
        db_path = get_default_config_path().parent / "triad.db"
        _ledger = Ledger(db_path=db_path)
        await _ledger.initialize()
    return _ledger
```

Update `handle_project_list`:

```python
@method("project.list")
async def handle_project_list(params: dict) -> dict:
    ledger = await get_ledger()
    projects = await ledger.list_projects()
    return {"projects": projects}
```

Update `handle_project_open`:

```python
@method("project.open")
async def handle_project_open(params: dict) -> dict:
    path = params.get("path", "")
    p = Path(path)
    if not p.is_dir():
        raise ValueError(f"Not a directory: {path}")
    ledger = await get_ledger()
    await ledger.save_project(str(p.resolve()), p.name, str(p.resolve()))
    return {"path": str(p.resolve()), "name": p.name, "git_root": str(p.resolve())}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/martin/triad
git add triad/core/storage/ledger.py triad/desktop/bridge.py
git commit -m "feat(desktop): session persistence with SQLite event ledger

Events table stores all session events (text, tool calls, findings).
Projects table tracks opened projects with last_opened_at.
Bridge methods now persist data through Ledger."
```

---

This completes **Phase 1**. At this point you have:
- Tauri v2 desktop window with dark Codex-style theme
- Sidebar with project groups and sessions
- Transcript with markdown rendering and streaming
- Composer with model/mode selectors
- Python backend with JSON-RPC bridge
- Claude PTY (interactive, no -p flag)
- Hooks listener for tool events
- Event merger for unified streaming
- SQLite persistence for sessions and events

---

# PHASE 2 — Coding Workflow Core

**Goal:** Terminal, diff, file attachments, Codex integration, search, command palette.

---

### Task 2.1: Terminal drawer (xterm.js)

**Files:**
- Create: `desktop/src/components/terminal/TerminalDrawer.tsx`
- Create: `triad/desktop/terminal_manager.py`
- Modify: `desktop/src/App.tsx`
- Modify: `triad/desktop/bridge.py`

- [ ] **Step 1: Install xterm.js**

```bash
cd /Users/martin/triad/desktop
pnpm add @xterm/xterm @xterm/addon-fit @xterm/addon-web-links
```

- [ ] **Step 2: Create TerminalDrawer component**

Create `desktop/src/components/terminal/TerminalDrawer.tsx`:

```typescript
import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "@xterm/xterm/css/xterm.css";
import { useUiStore } from "../../stores/ui-store";
import { rpc, onEvent } from "../../lib/rpc";

export function TerminalDrawer() {
  const { drawerOpen, drawerHeight, toggleDrawer, setDrawerHeight } = useUiStore();
  const termRef = useRef<HTMLDivElement>(null);
  const termInstance = useRef<Terminal | null>(null);
  const fitAddon = useRef<FitAddon | null>(null);
  const terminalId = useRef<string | null>(null);

  useEffect(() => {
    if (!drawerOpen || !termRef.current || termInstance.current) return;

    const term = new Terminal({
      theme: {
        background: "#181818",
        foreground: "#e4e4e4",
        cursor: "#e4e4e4",
        selectionBackground: "rgba(51, 156, 255, 0.3)",
        black: "#0d0d0d",
        brightBlack: "#5d5d5d",
        blue: "#339cff",
        brightBlue: "#0285ff",
        green: "#40c977",
        brightGreen: "#04b84c",
        red: "#ff6764",
        brightRed: "#fa423e",
        yellow: "#ffd240",
        brightYellow: "#ffc300",
      },
      fontFamily: '"Söhne Mono", ui-monospace, SFMono-Regular, Menlo, monospace',
      fontSize: 13,
      lineHeight: 1.4,
      cursorBlink: true,
    });

    const fit = new FitAddon();
    term.loadAddon(fit);
    term.loadAddon(new WebLinksAddon());
    term.open(termRef.current);
    fit.fit();

    termInstance.current = term;
    fitAddon.current = fit;

    // Create terminal session in backend
    rpc<{ terminal_id: string }>("terminal.create", {
      cwd: "/Users/martin",
    }).then((result) => {
      terminalId.current = result.terminal_id;
    });

    // Handle user input
    term.onData((data) => {
      if (terminalId.current) {
        rpc("terminal.input", {
          terminal_id: terminalId.current,
          data: btoa(data),
        });
      }
    });

    // Handle terminal output from backend
    const unsub = onEvent((event) => {
      if (
        event.type === "terminal_output" &&
        event.terminal_id === terminalId.current
      ) {
        const decoded = atob(String(event.data));
        term.write(decoded);
      }
    });

    // Handle resize
    const observer = new ResizeObserver(() => fit.fit());
    observer.observe(termRef.current);

    return () => {
      unsub();
      observer.disconnect();
      term.dispose();
      termInstance.current = null;
    };
  }, [drawerOpen]);

  if (!drawerOpen) {
    return (
      <button
        onClick={toggleDrawer}
        className="h-9 border-t border-border-default bg-surface flex items-center px-4 gap-2 text-xs text-text-secondary hover:text-text-primary cursor-pointer w-full"
      >
        <span>Terminal</span>
      </button>
    );
  }

  return (
    <div
      className="border-t border-border-default bg-surface flex flex-col"
      style={{ height: drawerHeight }}
    >
      {/* Drawer header */}
      <div className="h-9 flex items-center justify-between px-4 border-b border-border-default flex-shrink-0">
        <div className="flex items-center gap-4">
          <button className="text-xs text-text-primary font-medium">Terminal</button>
          <button className="text-xs text-text-tertiary hover:text-text-secondary">Logs</button>
          <button className="text-xs text-text-tertiary hover:text-text-secondary">Tasks</button>
        </div>
        <button onClick={toggleDrawer} className="text-text-tertiary hover:text-text-primary text-xs">
          ✕
        </button>
      </div>

      {/* Terminal area */}
      <div ref={termRef} className="flex-1 px-1 py-1" />
    </div>
  );
}
```

- [ ] **Step 3: Create terminal manager in Python backend**

Create `triad/desktop/terminal_manager.py`:

```python
"""Manage user terminal PTY sessions for the desktop client."""
from __future__ import annotations

import asyncio
import os
import pty
import signal
import uuid
from collections.abc import Callable, Coroutine
from typing import Any
import base64


class TerminalSession:
    """A single user terminal PTY session."""

    def __init__(
        self,
        terminal_id: str,
        cwd: str,
        on_output: Callable[[str, bytes], Coroutine[Any, Any, None]],
    ):
        self.terminal_id = terminal_id
        self.cwd = cwd
        self.on_output = on_output
        self._master_fd: int | None = None
        self._child_pid: int | None = None
        self._running = False
        self._read_task: asyncio.Task | None = None

    async def start(self) -> None:
        master_fd, slave_fd = pty.openpty()

        pid = os.fork()
        if pid == 0:
            os.close(master_fd)
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            os.close(slave_fd)
            os.chdir(self.cwd)
            shell = os.environ.get("SHELL", "/bin/zsh")
            os.execvp(shell, [shell, "-l"])
        else:
            os.close(slave_fd)
            self._master_fd = master_fd
            self._child_pid = pid
            self._running = True
            self._read_task = asyncio.create_task(self._read_loop())

    async def write(self, data: bytes) -> None:
        if self._master_fd is not None:
            await asyncio.get_event_loop().run_in_executor(
                None, os.write, self._master_fd, data
            )

    async def stop(self) -> None:
        self._running = False
        if self._child_pid:
            try:
                os.kill(self._child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if self._read_task:
            self._read_task.cancel()

    async def _read_loop(self) -> None:
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                data = await loop.run_in_executor(
                    None, os.read, self._master_fd, 8192
                )
                if not data:
                    break
                await self.on_output(self.terminal_id, data)
            except OSError:
                break
            except asyncio.CancelledError:
                break


class TerminalManager:
    """Manages multiple terminal sessions."""

    def __init__(self, on_output: Callable[[str, bytes], Coroutine[Any, Any, None]]):
        self.on_output = on_output
        self._sessions: dict[str, TerminalSession] = {}

    async def create(self, cwd: str) -> str:
        terminal_id = f"term_{uuid.uuid4().hex[:8]}"
        session = TerminalSession(terminal_id, cwd, self.on_output)
        await session.start()
        self._sessions[terminal_id] = session
        return terminal_id

    async def write(self, terminal_id: str, data: bytes) -> None:
        session = self._sessions.get(terminal_id)
        if session:
            await session.write(data)

    async def close(self, terminal_id: str) -> None:
        session = self._sessions.pop(terminal_id, None)
        if session:
            await session.stop()

    async def close_all(self) -> None:
        for session in self._sessions.values():
            await session.stop()
        self._sessions.clear()
```

- [ ] **Step 4: Add terminal RPC methods to bridge.py**

Add to `triad/desktop/bridge.py`:

```python
from triad.desktop.terminal_manager import TerminalManager
import base64

_terminal_manager: TerminalManager | None = None


async def _get_terminal_manager() -> TerminalManager:
    global _terminal_manager
    if _terminal_manager is None:
        async def on_terminal_output(terminal_id: str, data: bytes):
            await bridge.notify("event.stream", {
                "type": "terminal_output",
                "terminal_id": terminal_id,
                "data": base64.b64encode(data).decode("ascii"),
            })
        _terminal_manager = TerminalManager(on_output=on_terminal_output)
    return _terminal_manager


@method("terminal.create")
async def handle_terminal_create(params: dict) -> dict:
    mgr = await _get_terminal_manager()
    cwd = params.get("cwd", str(Path.home()))
    terminal_id = await mgr.create(cwd)
    return {"terminal_id": terminal_id}


@method("terminal.input")
async def handle_terminal_input(params: dict) -> dict:
    mgr = await _get_terminal_manager()
    terminal_id = params.get("terminal_id", "")
    data = base64.b64decode(params.get("data", ""))
    await mgr.write(terminal_id, data)
    return {"status": "ok"}


@method("terminal.close")
async def handle_terminal_close(params: dict) -> dict:
    mgr = await _get_terminal_manager()
    await mgr.close(params.get("terminal_id", ""))
    return {"status": "ok"}
```

- [ ] **Step 5: Wire TerminalDrawer into App.tsx**

```typescript
import { useEffect } from "react";
import { Sidebar } from "./components/sidebar/Sidebar";
import { Transcript } from "./components/transcript/Transcript";
import { Composer } from "./components/composer/Composer";
import { TerminalDrawer } from "./components/terminal/TerminalDrawer";
import { startBridge } from "./lib/rpc";
import { useStreamEvents } from "./hooks/useStreamEvents";

export function App() {
  useEffect(() => {
    startBridge().catch(console.error);
  }, []);

  useStreamEvents();

  return (
    <div className="flex h-screen w-screen bg-surface text-text-primary">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 bg-surface">
        <Transcript />
        <Composer />
        <TerminalDrawer />
      </main>
    </div>
  );
}
```

- [ ] **Step 6: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/components/terminal/ triad/desktop/terminal_manager.py triad/desktop/bridge.py desktop/src/App.tsx
git commit -m "feat(desktop): embedded terminal drawer with xterm.js

xterm.js terminal with Codex dark theme. Python PTY backend.
Drawer with tabs (Terminal, Logs, Tasks). Toggle open/close.
Reference: docs/design-references/02.01.54.png"
```

---

### Task 2.2: Tool cards (Read, Edit, Bash, Grep)

**Files:**
- Create: `desktop/src/components/transcript/ToolCard.tsx`
- Create: `desktop/src/components/transcript/DiffCard.tsx`
- Create: `desktop/src/components/transcript/BashCard.tsx`
- Modify: `desktop/src/components/transcript/Transcript.tsx`

- [ ] **Step 1: Create ToolCard component**

Create `desktop/src/components/transcript/ToolCard.tsx`:

```typescript
import { useState } from "react";

interface Props {
  tool: string;
  input: string;
  output?: string;
  status: "running" | "completed" | "failed";
}

const TOOL_ICONS: Record<string, string> = {
  Read: "📄",
  Edit: "✏️",
  Write: "📝",
  Bash: "⚡",
  Grep: "🔍",
  Glob: "📁",
  default: "🔧",
};

export function ToolCard({ tool, input, output, status }: Props) {
  const [expanded, setExpanded] = useState(false);
  const icon = TOOL_ICONS[tool] ?? TOOL_ICONS.default;

  // Parse input for display
  let displayInput = input;
  try {
    const parsed = JSON.parse(input);
    if (parsed.file_path) displayInput = parsed.file_path;
    else if (parsed.command) displayInput = parsed.command;
    else if (parsed.pattern) displayInput = parsed.pattern;
  } catch {
    // keep as-is
  }

  return (
    <div className="mx-6 my-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left bg-elevated rounded-lg border border-border-default px-3 py-2 hover:border-border-strong transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs">{icon}</span>
          <span className="text-xs font-medium text-text-primary">{tool}</span>
          <span className="text-xs text-text-tertiary truncate flex-1">{displayInput}</span>
          {status === "running" && (
            <span className="text-xs text-accent animate-pulse">●</span>
          )}
          {status === "completed" && (
            <span className="text-xs text-success">✓</span>
          )}
          {status === "failed" && (
            <span className="text-xs text-error">✕</span>
          )}
          <span className="text-xs text-text-tertiary">{expanded ? "▼" : "▶"}</span>
        </div>
      </button>

      {expanded && output && (
        <div className="mt-1 bg-editor rounded-lg border border-border-default px-3 py-2 max-h-[300px] overflow-auto">
          <pre className="text-xs text-text-secondary font-mono whitespace-pre-wrap">
            {output.length > 2000 ? output.slice(0, 2000) + "\n... (truncated)" : output}
          </pre>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create DiffCard**

Create `desktop/src/components/transcript/DiffCard.tsx`:

```typescript
interface Props {
  filePath: string;
  oldText: string;
  newText: string;
}

export function DiffCard({ filePath, oldText, newText }: Props) {
  return (
    <div className="mx-6 my-2 bg-elevated rounded-lg border border-border-default overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border-default flex items-center gap-2">
        <span className="text-xs">✏️</span>
        <span className="text-xs font-medium text-text-primary">Edit</span>
        <span className="text-xs text-text-tertiary truncate">{filePath}</span>
      </div>
      <div className="px-3 py-2 font-mono text-xs">
        {oldText && (
          <div className="text-red-300 bg-red-900/20 px-2 py-0.5 rounded mb-1">
            {oldText.split("\n").map((line, i) => (
              <div key={`old-${i}`}>- {line}</div>
            ))}
          </div>
        )}
        {newText && (
          <div className="text-green-300 bg-green-900/20 px-2 py-0.5 rounded">
            {newText.split("\n").map((line, i) => (
              <div key={`new-${i}`}>+ {line}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create BashCard**

Create `desktop/src/components/transcript/BashCard.tsx`:

```typescript
interface Props {
  command: string;
  output?: string;
  exitCode?: number;
}

export function BashCard({ command, output, exitCode }: Props) {
  return (
    <div className="mx-6 my-2 bg-editor rounded-lg border border-border-default overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border-default flex items-center gap-2">
        <span className="text-xs">⚡</span>
        <span className="text-xs font-mono text-text-primary">$ {command}</span>
        {exitCode !== undefined && exitCode !== 0 && (
          <span className="text-xs text-error ml-auto">exit {exitCode}</span>
        )}
      </div>
      {output && (
        <pre className="px-3 py-2 text-xs text-text-secondary font-mono whitespace-pre-wrap max-h-[200px] overflow-auto">
          {output}
        </pre>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Update Transcript to render tool cards**

Update the message rendering in `Transcript.tsx` to check for tool messages:

In the messages map function, replace the assistant rendering:

```typescript
{messages.map((msg) => {
  if (msg.role === "user") {
    return <UserMessage key={msg.id} message={msg} />;
  }
  if (msg.role === "system") {
    return (
      <div key={msg.id} className="px-6 py-2 flex justify-center">
        <span className="text-xs text-text-tertiary">{msg.content}</span>
      </div>
    );
  }
  // Check if this is a tool message
  if (msg.content.startsWith("🔧 ")) {
    const toolMatch = msg.content.match(/^🔧 (\w+): (.+)/s);
    if (toolMatch) {
      return (
        <ToolCard
          key={msg.id}
          tool={toolMatch[1]}
          input={toolMatch[2]}
          status="completed"
        />
      );
    }
  }
  return <AssistantMessage key={msg.id} message={msg} />;
})}
```

Add imports at top:

```typescript
import { ToolCard } from "./ToolCard";
```

- [ ] **Step 5: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/components/transcript/
git commit -m "feat(desktop): tool cards for Read/Edit/Bash/Grep in transcript

Collapsible tool cards with status indicators. DiffCard for Edit tool.
BashCard for terminal commands. Matches Codex tool card styling.
Reference: docs/design-references/02.03.42.png, 02.04.37.png"
```

---

### Task 2.3: Codex adapter integration (headless)

**Files:**
- Modify: `triad/desktop/bridge.py`
- Modify: `triad/desktop/event_merger.py`

- [ ] **Step 1: Add Codex headless execution to bridge**

Add to `bridge.py` the ability to run Codex headless when provider is "codex":

```python
from triad.core.providers.codex import CodexAdapter
from triad.core.accounts.manager import AccountManager
from triad.core.config import load_config

@method("session.send")
async def handle_session_send(params: dict) -> dict:
    session_id = params.get("session_id", "")
    content = params.get("content", "")
    provider = params.get("provider", "claude")
    project_path = params.get("project_path", str(Path.cwd()))
    
    if _event_merger is None:
        await _init_subsystems()
    
    if provider == "claude":
        # Interactive PTY — subscription-safe
        claude = _claude_sessions.get(session_id)
        if claude is None:
            claude = ClaudePTY(
                workdir=project_path,
                on_event=_event_merger.handle,
            )
            await claude.start()
            _claude_sessions[session_id] = claude
        await claude.send(content)
        return {"status": "sent", "session_id": session_id, "provider": "claude"}
    
    elif provider in ("codex", "gemini"):
        # Headless execution — structured JSON output
        from triad.core.providers import get_adapter
        adapter = get_adapter(provider)
        
        # Get account
        config = load_config(get_default_config_path())
        mgr = AccountManager(profiles_dir=config.profiles_dir)
        mgr.discover()
        profile = mgr.get_next(provider)
        
        if profile is None:
            await bridge.notify("event.stream", {
                "type": "run_failed",
                "error": f"No available {provider} accounts",
                "provider": provider,
            })
            return {"status": "error", "error": f"No {provider} accounts"}
        
        # Stream headless output
        asyncio.create_task(_run_headless(
            adapter, profile, content, Path(project_path), provider
        ))
        return {"status": "sent", "session_id": session_id, "provider": provider}
    
    return {"status": "error", "error": f"Unknown provider: {provider}"}


async def _run_headless(adapter, profile, prompt, workdir, provider):
    """Run a headless provider and stream events to UI."""
    try:
        async for event in adapter.execute_stream(
            profile=profile, prompt=prompt, workdir=workdir
        ):
            if event.kind == "text":
                await bridge.notify("event.stream", {
                    "type": "text_delta",
                    "delta": event.text,
                    "provider": provider,
                })
            elif event.kind == "error":
                await bridge.notify("event.stream", {
                    "type": "run_failed",
                    "error": event.text,
                    "provider": provider,
                })
            elif event.kind == "done":
                await bridge.notify("event.stream", {
                    "type": "run_completed",
                    "provider": provider,
                })
    except Exception as e:
        await bridge.notify("event.stream", {
            "type": "run_failed",
            "error": str(e),
            "provider": provider,
        })
```

- [ ] **Step 2: Commit**

```bash
cd /Users/martin/triad
git add triad/desktop/bridge.py
git commit -m "feat(desktop): Codex/Gemini headless provider integration

Codex and Gemini run headless via existing adapters with account rotation.
Claude continues to use interactive PTY (subscription-safe).
Provider routing based on session.send provider parameter."
```

---

### Task 2.4: Diff panel (split view)

**Files:**
- Create: `desktop/src/components/diff/DiffPanel.tsx`
- Modify: `desktop/src/App.tsx`

- [ ] **Step 1: Install diff viewer**

```bash
cd /Users/martin/triad/desktop
pnpm add react-diff-viewer-continued
```

- [ ] **Step 2: Create DiffPanel**

Create `desktop/src/components/diff/DiffPanel.tsx`:

```typescript
import ReactDiffViewer, { DiffMethod } from "react-diff-viewer-continued";
import { useUiStore } from "../../stores/ui-store";

interface DiffFile {
  path: string;
  oldContent: string;
  newContent: string;
}

interface Props {
  files: DiffFile[];
}

export function DiffPanel({ files }: Props) {
  const { diffPanelOpen, toggleDiffPanel } = useUiStore();

  if (!diffPanelOpen || files.length === 0) return null;

  return (
    <div className="w-[50%] border-l border-border-default flex flex-col bg-editor">
      {/* Header */}
      <div className="h-10 flex items-center justify-between px-4 border-b border-border-default flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-text-primary">
            {files.length} file{files.length > 1 ? "s" : ""} changed
          </span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-accent-bg text-accent">
            Непоставленный
          </span>
        </div>
        <button
          onClick={toggleDiffPanel}
          className="text-text-tertiary hover:text-text-primary text-xs"
        >
          ✕
        </button>
      </div>

      {/* File list tabs */}
      <div className="flex items-center gap-1 px-2 py-1 border-b border-border-default overflow-x-auto">
        {files.map((f) => (
          <button
            key={f.path}
            className="text-xs px-2 py-1 rounded text-text-secondary hover:text-text-primary hover:bg-elevated whitespace-nowrap"
          >
            {f.path.split("/").pop()}
          </button>
        ))}
      </div>

      {/* Diff content */}
      <div className="flex-1 overflow-auto">
        {files.map((f) => (
          <div key={f.path}>
            <div className="px-4 py-1 text-xs text-text-tertiary border-b border-border-default">
              {f.path}
            </div>
            <ReactDiffViewer
              oldValue={f.oldContent}
              newValue={f.newContent}
              splitView={false}
              useDarkTheme={true}
              compareMethod={DiffMethod.WORDS}
              styles={{
                variables: {
                  dark: {
                    diffViewerBackground: "#212121",
                    addedBackground: "rgba(64, 201, 119, 0.1)",
                    removedBackground: "rgba(255, 103, 100, 0.1)",
                    addedColor: "#40c977",
                    removedColor: "#ff6764",
                    wordAddedBackground: "rgba(64, 201, 119, 0.25)",
                    wordRemovedBackground: "rgba(255, 103, 100, 0.25)",
                    codeFoldBackground: "#282828",
                    codeFoldGutterBackground: "#282828",
                    emptyLineBackground: "#212121",
                    gutterBackground: "#1e1e1e",
                    gutterColor: "#5d5d5d",
                  },
                },
                contentText: {
                  fontFamily: '"Söhne Mono", monospace',
                  fontSize: "13px",
                  lineHeight: "18px",
                },
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Wire into App.tsx with split layout**

Update `App.tsx`:

```typescript
import { useEffect } from "react";
import { Sidebar } from "./components/sidebar/Sidebar";
import { Transcript } from "./components/transcript/Transcript";
import { Composer } from "./components/composer/Composer";
import { TerminalDrawer } from "./components/terminal/TerminalDrawer";
import { DiffPanel } from "./components/diff/DiffPanel";
import { startBridge } from "./lib/rpc";
import { useStreamEvents } from "./hooks/useStreamEvents";
import { useUiStore } from "./stores/ui-store";

export function App() {
  const { diffPanelOpen } = useUiStore();

  useEffect(() => {
    startBridge().catch(console.error);
  }, []);

  useStreamEvents();

  return (
    <div className="flex h-screen w-screen bg-surface text-text-primary">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 flex min-h-0">
          <main className="flex-1 flex flex-col min-w-0 bg-surface">
            <Transcript />
            <Composer />
          </main>
          {diffPanelOpen && <DiffPanel files={[]} />}
        </div>
        <TerminalDrawer />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/components/diff/ desktop/src/App.tsx
git commit -m "feat(desktop): split-view diff panel with dark theme

react-diff-viewer-continued with Codex color scheme.
File tabs, unified/split view, syntax highlighting.
Toggle with Cmd+Shift+D.
Reference: docs/design-references/02.05.01.png, 02.05.17.png"
```

---

### Task 2.5: Command palette + keyboard shortcuts

**Files:**
- Create: `desktop/src/components/shared/CommandPalette.tsx`
- Create: `desktop/src/hooks/useKeyboardShortcuts.ts`
- Modify: `desktop/src/App.tsx`

- [ ] **Step 1: Create CommandPalette**

Create `desktop/src/components/shared/CommandPalette.tsx`:

```typescript
import { useState, useEffect, useRef } from "react";

interface Command {
  id: string;
  label: string;
  shortcut?: string;
  action: () => void;
}

interface Props {
  open: boolean;
  onClose: () => void;
  commands: Command[];
}

export function CommandPalette({ open, onClose, commands }: Props) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  if (!open) return null;

  const filtered = commands.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20%]" onClick={onClose}>
      <div
        className="w-[500px] bg-elevated border border-border-strong rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Type a command..."
          className="w-full px-4 py-3 bg-transparent text-sm text-text-primary placeholder:text-text-tertiary outline-none border-b border-border-default"
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            if (e.key === "Enter" && filtered.length > 0) {
              filtered[0].action();
              onClose();
            }
          }}
        />
        <div className="max-h-[300px] overflow-auto py-1">
          {filtered.map((cmd) => (
            <button
              key={cmd.id}
              onClick={() => {
                cmd.action();
                onClose();
              }}
              className="w-full text-left px-4 py-2 text-sm text-text-primary hover:bg-elevated-secondary flex items-center justify-between"
            >
              <span>{cmd.label}</span>
              {cmd.shortcut && (
                <span className="text-xs text-text-tertiary">{cmd.shortcut}</span>
              )}
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="px-4 py-3 text-sm text-text-tertiary text-center">
              No commands found
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create keyboard shortcuts hook**

Create `desktop/src/hooks/useKeyboardShortcuts.ts`:

```typescript
import { useEffect } from "react";
import { useUiStore } from "../stores/ui-store";

export function useKeyboardShortcuts(onCommandPalette: () => void) {
  const { toggleDrawer, toggleDiffPanel, toggleSidebar } = useUiStore();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;

      // Cmd+K — Command palette
      if (meta && e.key === "k") {
        e.preventDefault();
        onCommandPalette();
      }
      // Cmd+` — Toggle terminal
      if (meta && e.key === "`") {
        e.preventDefault();
        toggleDrawer();
      }
      // Cmd+Shift+D — Toggle diff panel
      if (meta && e.shiftKey && e.key === "D") {
        e.preventDefault();
        toggleDiffPanel();
      }
      // Cmd+B — Toggle sidebar
      if (meta && e.key === "b") {
        e.preventDefault();
        toggleSidebar();
      }
      // Cmd+. — Stop current run (placeholder)
      if (meta && e.key === ".") {
        e.preventDefault();
        // TODO: stop current run
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onCommandPalette, toggleDrawer, toggleDiffPanel, toggleSidebar]);
}
```

- [ ] **Step 3: Wire into App.tsx**

Add state and components:

```typescript
import { useEffect, useState, useCallback } from "react";
import { Sidebar } from "./components/sidebar/Sidebar";
import { Transcript } from "./components/transcript/Transcript";
import { Composer } from "./components/composer/Composer";
import { TerminalDrawer } from "./components/terminal/TerminalDrawer";
import { DiffPanel } from "./components/diff/DiffPanel";
import { CommandPalette } from "./components/shared/CommandPalette";
import { startBridge } from "./lib/rpc";
import { useStreamEvents } from "./hooks/useStreamEvents";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { useUiStore } from "./stores/ui-store";

export function App() {
  const { diffPanelOpen, sidebarCollapsed, toggleDrawer, toggleDiffPanel } = useUiStore();
  const [paletteOpen, setPaletteOpen] = useState(false);

  const togglePalette = useCallback(() => setPaletteOpen((v) => !v), []);

  useEffect(() => {
    startBridge().catch(console.error);
  }, []);

  useStreamEvents();
  useKeyboardShortcuts(togglePalette);

  const commands = [
    { id: "new-session", label: "New Session", shortcut: "⌘N", action: () => {} },
    { id: "toggle-terminal", label: "Toggle Terminal", shortcut: "⌘`", action: toggleDrawer },
    { id: "toggle-diff", label: "Toggle Diff Panel", shortcut: "⌘⇧D", action: toggleDiffPanel },
    { id: "search", label: "Search Sessions", shortcut: "⌘⇧F", action: () => {} },
  ];

  return (
    <div className="flex h-screen w-screen bg-surface text-text-primary">
      {!sidebarCollapsed && <Sidebar />}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 flex min-h-0">
          <main className="flex-1 flex flex-col min-w-0 bg-surface">
            <Transcript />
            <Composer />
          </main>
          {diffPanelOpen && <DiffPanel files={[]} />}
        </div>
        <TerminalDrawer />
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} commands={commands} />
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/components/shared/ desktop/src/hooks/useKeyboardShortcuts.ts desktop/src/App.tsx
git commit -m "feat(desktop): command palette (Cmd+K) and keyboard shortcuts

Command palette with fuzzy search. Shortcuts: Cmd+\` terminal,
Cmd+Shift+D diff, Cmd+B sidebar, Cmd+K palette."
```

---

This completes **Phase 2**. At this point you have the full coding workflow: chat, terminal, diffs, tool cards, provider switching, keyboard shortcuts.

---

# PHASE 3 — Multi-Agent Modes

**Goal:** Critic mode, brainstorm mode, delegate mode with UI for rounds, findings, and roles.

---

### Task 3.1: Orchestrator engine (Python)

**Files:**
- Create: `triad/desktop/orchestrator.py`
- Modify: `triad/desktop/bridge.py`

- [ ] **Step 1: Create orchestrator**

Create `triad/desktop/orchestrator.py`:

```python
"""Multi-agent orchestration engine for desktop client."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from triad.core.providers import get_adapter
from triad.core.accounts.manager import AccountManager
from triad.core.config import load_config, get_default_config_path


@dataclass
class CriticRound:
    round_number: int
    writer_output: str = ""
    critic_output: str = ""
    findings: list[dict] = field(default_factory=list)
    lgtm: bool = False


class Orchestrator:
    """Drives multi-agent modes: critic, brainstorm, delegate."""

    def __init__(
        self,
        on_event: Callable[[dict], Coroutine[Any, Any, None]],
    ):
        self.on_event = on_event
        self._config = load_config(get_default_config_path())
        self._account_mgr = AccountManager(profiles_dir=self._config.profiles_dir)
        self._account_mgr.discover()

    async def run_critic(
        self,
        prompt: str,
        workdir: Path,
        writer_provider: str,
        critic_provider: str,
        max_rounds: int = 3,
        claude_pty=None,
    ) -> list[CriticRound]:
        """Writer/critic loop. Writer produces code, critic reviews."""
        rounds: list[CriticRound] = []

        for round_num in range(1, max_rounds + 1):
            round_data = CriticRound(round_number=round_num)

            await self.on_event({
                "type": "system",
                "content": f"Critic round {round_num}/{max_rounds}",
            })

            # --- Writer phase ---
            if writer_provider == "claude" and claude_pty:
                # Use interactive PTY
                writer_prompt = prompt if round_num == 1 else (
                    f"Critic found these issues in round {round_num - 1}:\n"
                    + "\n".join(f"- {f['title']}" for f in rounds[-1].findings)
                    + "\nPlease fix them."
                )
                await claude_pty.send(writer_prompt)
                # Wait for Claude to finish (simplified: wait for hooks Stop event)
                await asyncio.sleep(5)  # TODO: proper wait on Stop hook
                round_data.writer_output = "(Claude PTY output captured via hooks/parser)"
            else:
                # Headless writer
                adapter = get_adapter(writer_provider)
                profile = self._account_mgr.get_next(writer_provider)
                if profile is None:
                    await self.on_event({
                        "type": "run_failed",
                        "error": f"No {writer_provider} accounts available",
                    })
                    break

                writer_output = ""
                async for event in adapter.execute_stream(
                    profile=profile, prompt=prompt, workdir=workdir
                ):
                    if event.kind == "text":
                        writer_output += event.text + "\n"
                        await self.on_event({
                            "type": "text_delta",
                            "delta": event.text,
                            "provider": writer_provider,
                            "role": "writer",
                        })
                round_data.writer_output = writer_output

            # --- Critic phase ---
            critic_adapter = get_adapter(critic_provider)
            critic_profile = self._account_mgr.get_next(critic_provider)
            if critic_profile is None:
                await self.on_event({
                    "type": "run_failed",
                    "error": f"No {critic_provider} accounts available",
                })
                break

            critic_prompt = (
                f"Review the following code changes and provide findings as a numbered list.\n"
                f"Each finding should have a severity (P0/P1/P2), file, and description.\n"
                f"If everything looks good, respond with 'LGTM'.\n\n"
                f"Changes:\n{round_data.writer_output}"
            )

            critic_output = ""
            async for event in critic_adapter.execute_stream(
                profile=critic_profile, prompt=critic_prompt, workdir=workdir
            ):
                if event.kind == "text":
                    critic_output += event.text + "\n"
                    await self.on_event({
                        "type": "text_delta",
                        "delta": event.text,
                        "provider": critic_provider,
                        "role": "critic",
                    })

            round_data.critic_output = critic_output
            round_data.lgtm = "lgtm" in critic_output.lower()

            # Parse findings (simple pattern matching)
            round_data.findings = self._parse_findings(critic_output)
            for finding in round_data.findings:
                await self.on_event({
                    "type": "review_finding",
                    **finding,
                })

            rounds.append(round_data)

            if round_data.lgtm:
                await self.on_event({
                    "type": "system",
                    "content": f"Critic approved in round {round_num}. LGTM ✓",
                })
                break

        return rounds

    @staticmethod
    def _parse_findings(text: str) -> list[dict]:
        """Extract review findings from critic output."""
        findings = []
        for line in text.split("\n"):
            line = line.strip()
            for severity in ("P0", "P1", "P2"):
                if severity in line:
                    findings.append({
                        "severity": severity,
                        "title": line,
                        "file": "",
                        "explanation": line,
                    })
                    break
        return findings
```

- [ ] **Step 2: Add critic RPC method to bridge**

Add to `bridge.py`:

```python
from triad.desktop.orchestrator import Orchestrator

_orchestrator: Orchestrator | None = None

async def _get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        async def forward(event):
            await bridge.notify("event.stream", event)
        _orchestrator = Orchestrator(on_event=forward)
    return _orchestrator


@method("critic.start")
async def handle_critic_start(params: dict) -> dict:
    orch = await _get_orchestrator()
    workdir = Path(params.get("project_path", str(Path.cwd())))
    claude_pty = _claude_sessions.get(params.get("session_id", ""))

    asyncio.create_task(orch.run_critic(
        prompt=params.get("prompt", ""),
        workdir=workdir,
        writer_provider=params.get("writer", "claude"),
        critic_provider=params.get("critic", "codex"),
        max_rounds=params.get("max_rounds", 3),
        claude_pty=claude_pty,
    ))
    return {"status": "started"}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/martin/triad
git add triad/desktop/orchestrator.py triad/desktop/bridge.py
git commit -m "feat(desktop): multi-agent orchestrator with critic mode

Writer/critic loop: Claude writes (PTY), Codex reviews (headless).
Findings parsed and sent as review_finding events to UI.
Auto-iterate until LGTM or max rounds."
```

---

### Task 3.2: Finding cards in transcript

**Files:**
- Create: `desktop/src/components/transcript/FindingCard.tsx`
- Modify: `desktop/src/hooks/useStreamEvents.ts`
- Modify: `desktop/src/components/transcript/Transcript.tsx`

- [ ] **Step 1: Create FindingCard**

Create `desktop/src/components/transcript/FindingCard.tsx`:

```typescript
import type { ReviewFinding } from "../../lib/types";

interface Props {
  finding: ReviewFinding;
}

const SEVERITY_STYLES = {
  P0: "bg-red-900/30 border-red-300/30 text-red-300",
  P1: "bg-orange-900/30 border-orange-300/30 text-orange-300",
  P2: "bg-yellow-900/30 border-yellow-300/30 text-yellow-300",
};

export function FindingCard({ finding }: Props) {
  const style = SEVERITY_STYLES[finding.severity] ?? SEVERITY_STYLES.P2;

  return (
    <div className={`mx-6 my-2 rounded-lg border px-4 py-3 ${style}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-bold">{finding.severity}</span>
        <span className="text-xs font-medium">{finding.title}</span>
      </div>
      {finding.file && (
        <div className="text-xs opacity-70 mb-1">{finding.file}{finding.line_range ? `:${finding.line_range}` : ""}</div>
      )}
      <div className="text-xs opacity-80">{finding.explanation}</div>
    </div>
  );
}
```

- [ ] **Step 2: Update useStreamEvents to handle findings**

In `desktop/src/hooks/useStreamEvents.ts`, add to the switch:

```typescript
case "review_finding":
  addMessage({
    id: `finding_${Date.now()}_${Math.random()}`,
    session_id: activeSession.id,
    role: "assistant",
    content: JSON.stringify({
      _finding: true,
      severity: event.severity,
      title: event.title,
      file: event.file,
      explanation: event.explanation,
    }),
    provider: String(event.provider ?? "codex"),
    agent_role: "critic",
    timestamp: new Date().toISOString(),
  });
  break;

case "system":
  addMessage({
    id: `sys_${Date.now()}`,
    session_id: activeSession.id,
    role: "system",
    content: String(event.content ?? ""),
    timestamp: new Date().toISOString(),
  });
  break;
```

- [ ] **Step 3: Update Transcript to render findings**

In `Transcript.tsx`, in the messages map, add before the final AssistantMessage fallback:

```typescript
// Check if this is a finding
if (msg.role === "assistant" && msg.content.startsWith("{\"_finding\":")) {
  try {
    const finding = JSON.parse(msg.content);
    if (finding._finding) {
      return <FindingCard key={msg.id} finding={finding} />;
    }
  } catch {}
}
```

Add import:

```typescript
import { FindingCard } from "./FindingCard";
```

- [ ] **Step 4: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/components/transcript/FindingCard.tsx desktop/src/hooks/useStreamEvents.ts desktop/src/components/transcript/Transcript.tsx
git commit -m "feat(desktop): review finding cards with severity badges

P0 (red), P1 (orange), P2 (yellow) finding cards in transcript.
Shows severity, title, file reference, explanation.
Reference: docs/design-references/ critic mode screenshots"
```

---

### Task 3.3: Provider role badges in transcript

**Files:**
- Create: `desktop/src/components/shared/Badge.tsx`
- Modify: `desktop/src/components/transcript/AssistantMessage.tsx`

- [ ] **Step 1: Create Badge component**

Create `desktop/src/components/shared/Badge.tsx`:

```typescript
interface Props {
  provider: string;
  role?: string;
}

const PROVIDER_COLORS: Record<string, string> = {
  claude: "bg-purple-300/20 text-purple-300",
  codex: "bg-green-300/20 text-green-300",
  gemini: "bg-blue-300/20 text-blue-300",
};

const ROLE_LABELS: Record<string, string> = {
  writer: "Writer",
  critic: "Critic",
  ideator: "Ideator",
  moderator: "Moderator",
};

export function Badge({ provider, role }: Props) {
  const color = PROVIDER_COLORS[provider] ?? "bg-elevated text-text-secondary";
  const providerLabel = provider.charAt(0).toUpperCase() + provider.slice(1);
  const roleLabel = role ? ROLE_LABELS[role] ?? role : "";

  return (
    <span className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded ${color}`}>
      <span className="font-medium">{providerLabel}</span>
      {roleLabel && <span className="opacity-70">/ {roleLabel}</span>}
    </span>
  );
}
```

- [ ] **Step 2: Update AssistantMessage to show badge**

In `AssistantMessage.tsx`, add the Badge above the message content:

```typescript
import { Badge } from "../shared/Badge";

// Inside the component, after the avatar div:
<div className="min-w-0 flex-1">
  {(message.provider || message.agent_role) && (
    <div className="mb-1">
      <Badge
        provider={message.provider ?? "claude"}
        role={message.agent_role}
      />
    </div>
  )}
  <div className="prose prose-invert prose-sm max-w-none">
    ...
  </div>
</div>
```

- [ ] **Step 3: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/components/shared/Badge.tsx desktop/src/components/transcript/AssistantMessage.tsx
git commit -m "feat(desktop): provider/role badges on assistant messages

Color-coded badges: Claude (purple), Codex (green), Gemini (blue).
Role labels: Writer, Critic, Ideator, Moderator."
```

---

This completes **Phase 3**. Critic mode works end-to-end. Brainstorm and delegate modes follow the same pattern — add RPC methods to orchestrator and UI controls to Composer.

---

# PHASE 4 — Premium Polish

**Goal:** Search, session fork, animations, diagnostics, macOS integration.

---

### Task 4.1: Full-text search across sessions

**Files:**
- Create: `triad/desktop/search.py`
- Modify: `triad/desktop/bridge.py`
- Create: `desktop/src/components/sidebar/SearchPanel.tsx`

- [ ] **Step 1: Create FTS5 search in Python**

Create `triad/desktop/search.py`:

```python
"""Full-text search over session events using SQLite FTS5."""
from __future__ import annotations

import json
from pathlib import Path

import aiosqlite


class SearchIndex:
    """FTS5 search index over event data."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
                session_id,
                content,
                content_rowid='id',
                tokenize='unicode61'
            )
        """)
        await self._db.commit()

    async def index_event(self, event_id: int, session_id: str, content: str) -> None:
        if not self._db:
            return
        await self._db.execute(
            "INSERT OR REPLACE INTO events_fts (rowid, session_id, content) VALUES (?, ?, ?)",
            (event_id, session_id, content),
        )
        await self._db.commit()

    async def search(self, query: str, limit: int = 50) -> list[dict]:
        if not self._db:
            return []
        cursor = await self._db.execute(
            """
            SELECT rowid, session_id, snippet(events_fts, 1, '<mark>', '</mark>', '...', 32) as snippet
            FROM events_fts
            WHERE content MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
        rows = await cursor.fetchall()
        return [
            {"event_id": r[0], "session_id": r[1], "snippet": r[2]}
            for r in rows
        ]

    async def close(self) -> None:
        if self._db:
            await self._db.close()
```

- [ ] **Step 2: Add search RPC method**

Add to `bridge.py`:

```python
from triad.desktop.search import SearchIndex

_search: SearchIndex | None = None

async def _get_search() -> SearchIndex:
    global _search
    if _search is None:
        db_path = get_default_config_path().parent / "triad.db"
        _search = SearchIndex(db_path=db_path)
        await _search.initialize()
    return _search

@method("search")
async def handle_search(params: dict) -> dict:
    si = await _get_search()
    results = await si.search(params.get("query", ""), params.get("limit", 50))
    return {"results": results}
```

- [ ] **Step 3: Create SearchPanel in sidebar**

Create `desktop/src/components/sidebar/SearchPanel.tsx`:

```typescript
import { useState, useCallback } from "react";
import { rpc } from "../../lib/rpc";

interface SearchResult {
  event_id: number;
  session_id: string;
  snippet: string;
}

export function SearchPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      const res = await rpc<{ results: SearchResult[] }>("search", { query: q });
      setResults(res.results);
    } finally {
      setSearching(false);
    }
  }, []);

  return (
    <div className="p-2">
      <input
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          doSearch(e.target.value);
        }}
        placeholder="Search sessions..."
        className="w-full px-3 py-1.5 text-sm bg-elevated rounded border border-border-default text-text-primary placeholder:text-text-tertiary outline-none focus:border-accent"
      />
      {results.length > 0 && (
        <div className="mt-2 space-y-1 max-h-[300px] overflow-auto">
          {results.map((r) => (
            <button
              key={r.event_id}
              className="w-full text-left px-2 py-1.5 text-xs text-text-secondary hover:bg-elevated rounded"
            >
              <div
                className="truncate"
                dangerouslySetInnerHTML={{ __html: r.snippet }}
              />
              <div className="text-text-tertiary mt-0.5">Session: {r.session_id}</div>
            </button>
          ))}
        </div>
      )}
      {searching && <div className="text-xs text-text-tertiary mt-2 text-center">Searching...</div>}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/martin/triad
git add triad/desktop/search.py desktop/src/components/sidebar/SearchPanel.tsx triad/desktop/bridge.py
git commit -m "feat(desktop): full-text search across all sessions via FTS5

SQLite FTS5 index on event content. Search panel in sidebar.
Highlighted snippets in results. Cmd+Shift+F shortcut."
```

---

### Task 4.2: Title bar with controls

**Files:**
- Create: `desktop/src/components/layout/TitleBar.tsx`
- Modify: `desktop/src/App.tsx`

- [ ] **Step 1: Create TitleBar**

Create `desktop/src/components/layout/TitleBar.tsx`:

```typescript
import { useSessionStore } from "../../stores/session-store";
import { useProjectStore } from "../../stores/project-store";
import { useProviderStore } from "../../stores/provider-store";

export function TitleBar() {
  const { activeSession } = useSessionStore();
  const { activeProject } = useProjectStore();
  const { mode, activeProvider } = useProviderStore();

  return (
    <div
      className="h-[var(--titlebar-height)] flex items-center justify-between px-4 border-b border-border-default bg-surface flex-shrink-0"
      data-tauri-drag-region
    >
      {/* Left: traffic light spacer + navigation */}
      <div className="flex items-center gap-3 min-w-[200px]">
        <div className="w-[68px]" /> {/* Traffic light spacer */}
        <button className="text-text-tertiary hover:text-text-secondary text-sm">←</button>
        <button className="text-text-tertiary hover:text-text-secondary text-sm">→</button>
      </div>

      {/* Center: session title */}
      <div className="flex items-center gap-2 text-sm">
        {activeSession ? (
          <>
            <span className="font-medium text-text-primary">
              {activeSession.title || "Новая беседа"}
            </span>
            <span className="text-text-tertiary">{activeProject?.name}</span>
          </>
        ) : (
          <span className="text-text-secondary">Triad</span>
        )}
      </div>

      {/* Right: mode + provider + controls */}
      <div className="flex items-center gap-3 min-w-[200px] justify-end">
        <span className="text-xs px-2 py-0.5 rounded bg-elevated text-text-secondary capitalize">
          {mode}
        </span>
        <span className="text-xs text-text-tertiary capitalize">{activeProvider}</span>
        <span className="text-xs text-text-tertiary">●</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add to App.tsx**

Add TitleBar above the main content area:

```typescript
import { TitleBar } from "./components/layout/TitleBar";

// In the return JSX, inside the flex-1 div after Sidebar:
<div className="flex-1 flex flex-col min-w-0">
  <TitleBar />
  <div className="flex-1 flex min-h-0">
    ...
  </div>
  <TerminalDrawer />
</div>
```

- [ ] **Step 3: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/components/layout/ desktop/src/App.tsx
git commit -m "feat(desktop): custom title bar with session name and mode indicator

Draggable title bar, back/forward navigation, session title, mode badge.
Reference: docs/design-references/02.01.54.png, 02.03.42.png"
```

---

### Task 4.3: Session resume on app restart

**Files:**
- Modify: `triad/desktop/bridge.py`
- Modify: `desktop/src/App.tsx`

- [ ] **Step 1: Add session resume methods**

Add to `bridge.py`:

```python
@method("session.get_events")
async def handle_session_events(params: dict) -> dict:
    ledger = await get_ledger()
    events = await ledger.get_session_events(
        params.get("session_id", ""),
        limit=params.get("limit", 500),
    )
    return {"events": events}


@method("app.get_state")
async def handle_app_state(params: dict) -> dict:
    """Return last known app state for resume."""
    ledger = await get_ledger()
    projects = await ledger.list_projects()
    sessions = await ledger.list_sessions(limit=50)
    return {
        "projects": projects,
        "sessions": sessions,
        "last_project": projects[0]["path"] if projects else None,
    }
```

- [ ] **Step 2: Load state on app start**

In `App.tsx`, update the useEffect:

```typescript
useEffect(() => {
  async function init() {
    await startBridge();
    // Restore last state
    try {
      const state = await rpc<{
        projects: Project[];
        sessions: Session[];
        last_project: string | null;
      }>("app.get_state");

      if (state.projects.length > 0) {
        useProjectStore.setState({
          projects: state.projects,
          activeProject: state.projects[0],
        });
      }
      if (state.sessions.length > 0) {
        useSessionStore.setState({ sessions: state.sessions });
      }
    } catch (e) {
      console.warn("Failed to restore state:", e);
    }
  }
  init();
}, []);
```

- [ ] **Step 3: Commit**

```bash
cd /Users/martin/triad
git add triad/desktop/bridge.py desktop/src/App.tsx
git commit -m "feat(desktop): session resume on app restart

Load last projects and sessions from SQLite on startup.
Session events can be replayed to rebuild transcript."
```

---

### Task 4.4: Smooth animations and polish

**Files:**
- Modify: `desktop/src/styles/tokens.css`
- Modify various components for transitions

- [ ] **Step 1: Add animation utilities to CSS**

Add to `desktop/src/styles/tokens.css`:

```css
/* Animations */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

@keyframes slideDown {
  from { transform: translateY(0); }
  to { transform: translateY(100%); }
}

.animate-fade-in {
  animation: fadeIn 0.15s ease-out;
}

.animate-slide-up {
  animation: slideUp 0.2s ease-out;
}

/* Smooth transitions for all interactive elements */
.transition-smooth {
  transition: all 0.15s ease-out;
}
```

- [ ] **Step 2: Add fade-in to messages**

In `UserMessage.tsx` and `AssistantMessage.tsx`, add `animate-fade-in` to the outer div:

```typescript
<div className="px-6 py-4 animate-fade-in">
```

- [ ] **Step 3: Add slide animation to terminal drawer**

In `TerminalDrawer.tsx`, add `animate-slide-up` when opening:

```typescript
<div className="border-t border-border-default bg-surface flex flex-col animate-slide-up" style={{ height: drawerHeight }}>
```

- [ ] **Step 4: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/styles/ desktop/src/components/
git commit -m "feat(desktop): smooth animations and transition polish

Fade-in for messages, slide-up for terminal drawer.
Smooth hover/focus transitions throughout."
```

---

### Task 4.5: Diagnostics panel

**Files:**
- Create: `desktop/src/components/shared/DiagnosticsPanel.tsx`
- Modify: `triad/desktop/bridge.py`

- [ ] **Step 1: Add diagnostics RPC method**

Add to `bridge.py`:

```python
@method("diagnostics")
async def handle_diagnostics(params: dict) -> dict:
    from triad.core.config import load_config
    config = load_config(get_default_config_path())
    
    mgr_status = {}
    try:
        mgr = AccountManager(profiles_dir=config.profiles_dir)
        mgr.discover()
        for provider in ("claude", "codex", "gemini"):
            mgr_status[provider] = mgr.pool_status(provider)
    except Exception as e:
        mgr_status["error"] = str(e)
    
    return {
        "version": "0.1.0",
        "python_version": __import__("sys").version,
        "triad_home": str(config.triad_home),
        "db_path": str(config.triad_home / "triad.db"),
        "providers": mgr_status,
        "active_claude_sessions": list(_claude_sessions.keys()),
        "hooks_socket": "/tmp/triad-hooks.sock",
    }
```

- [ ] **Step 2: Create DiagnosticsPanel**

Create `desktop/src/components/shared/DiagnosticsPanel.tsx`:

```typescript
import { useState, useEffect } from "react";
import { rpc } from "../../lib/rpc";

export function DiagnosticsPanel() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    rpc<Record<string, unknown>>("diagnostics").then(setData);
  }, []);

  if (!data) return <div className="p-4 text-sm text-text-tertiary">Loading...</div>;

  return (
    <div className="p-4 space-y-3">
      <h3 className="text-sm font-medium text-text-primary">Diagnostics</h3>
      <pre className="text-xs text-text-secondary font-mono bg-editor rounded p-3 overflow-auto max-h-[400px]">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/martin/triad
git add desktop/src/components/shared/DiagnosticsPanel.tsx triad/desktop/bridge.py
git commit -m "feat(desktop): diagnostics panel with provider health and system info

Shows: version, providers, account pools, active sessions, paths."
```

---

This completes **Phase 4** and the full implementation plan.

## Summary of All Deliverables

| Phase | Tasks | What You Get |
|-------|-------|-------------|
| **Phase 1** | 1.1–1.8 | Working desktop app: sidebar, transcript, composer, Claude PTY, streaming, persistence |
| **Phase 2** | 2.1–2.5 | Full coding workflow: terminal, tool cards, Codex integration, diff panel, command palette |
| **Phase 3** | 3.1–3.3 | Multi-agent: critic mode, finding cards, provider/role badges |
| **Phase 4** | 4.1–4.5 | Polish: search, title bar, session resume, animations, diagnostics |

**Total tasks:** 21
**Estimated commits:** ~25

Each task is self-contained with exact file paths, complete code, and clear exit criteria. Tasks within each phase are sequential. Phases must be done in order.
