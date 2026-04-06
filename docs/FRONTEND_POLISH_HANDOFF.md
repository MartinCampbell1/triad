# Frontend Polish Handoff — Triad Desktop

## Context

Triad Desktop is a native Mac desktop client (Tauri + React 19 + TypeScript + Tailwind 4 + Vite + Zustand) that wraps a Python multi-agent backend. The frontend was rewritten to be a 1:1 visual clone of **Codex Desktop** (OpenAI's native Mac app). The rewrite is ~80% done — structure and layout match Codex, but the user says it's "still raw" and needs polish.

**All uncommitted changes live in `/Users/martin/triad/desktop/src/`** (the main repo, NOT the worktree). There are 24 modified files and 3 new files (CommitDialog.tsx, FileChangeSummary.tsx, TriadLogo.tsx). Nothing has been committed yet.

## Reference Material

- **Codex Desktop screenshots**: `/Users/martin/triad/docs/design-references/` — 20+ screenshots of the real Codex Desktop app showing every screen
- **Logo preview**: `/Users/martin/triad/desktop/logo-preview.html` — open in browser to see the Triad trefoil logo at different sizes
- **Previous design doc**: `/Users/martin/triad/docs/DESIGN_SYSTEM.md`
- **To compare live**: The Codex Desktop app is installed on this Mac — use computer-use to screenshot it

## Tech Stack

- React 19.1.0, TypeScript 5.8.3, Tailwind CSS 4.1.1, Vite 6.3.5, Zustand 5.0.6
- @tanstack/react-virtual for transcript virtual scrolling
- xterm.js for terminal emulation
- Lazy-loaded: DiffPanel, CommandPalette, Markdown
- CSS tokens in `desktop/src/styles/tokens.css`
- No CSS modules — everything is Tailwind utility classes

## Dev Server

```bash
cd /Users/martin/triad/desktop
corepack pnpm dev --host 127.0.0.1 --port 1420
```

Or via Claude Preview MCP (launch.json already configured at `/Users/martin/triad/.claude/worktrees/upbeat-feynman/.claude/launch.json`).

TypeScript check:
```bash
/usr/local/bin/node /Users/martin/triad/desktop/node_modules/typescript/bin/tsc --noEmit --project /Users/martin/triad/desktop/tsconfig.json
```

Note: `pnpm` must be invoked via corepack. Direct `pnpm` may not be in PATH. Use `/usr/local/bin/node /usr/local/lib/node_modules/corepack/shims/pnpm` if needed.

## What Was Done (Completed)

### 1. Design Tokens (`tokens.css`)
- Removed ALL decorative animations (codex-fade-in-up, codex-soft-glow, etc.)
- Removed radial gradient from body
- Sidebar width: 260px (was 296px)
- Clean gray scale, blue/green/red/orange accent colors
- Simplified border colors using `color-mix`

### 2. Title Bar (`TitleBar.tsx`) — REWRITTEN
- Native macOS traffic lights area (78px left padding)
- SVG icon buttons: sidebar toggle, back/forward arrows
- Center: session title + project name + "..." menu
- Right: Run, Split view, "Переместить в рабочее дерево", "Совершить ▾" commit button, open externally, download, share icons, diff stats (+N/-N)
- `data-tauri-drag-region` for native window dragging

### 3. Sidebar (`Sidebar.tsx`) — REWRITTEN
- Top nav: pen=Новая беседа, grid=Навыки и приложения, clock=Автоматизации (all SVG icons)
- Search with magnifying glass icon
- "Беседы" header with 4 icon buttons (collapse-all, filter, refresh, add project)
- Flat `bg-[var(--color-bg-surface)]` background
- 52px top padding for native title bar area

### 4. Composer (`Composer.tsx`) — REWRITTEN
- Rounded-[18px] container, subtle border
- Textarea: "Запросите внесение дополнительных изменений"
- Controls: "+" attach, ModelSelector (plain text), "Очень высокий" reasoning selector (plain text with ▾)
- Right: mic SVG, white send button (bg-white/90, up-arrow icon)
- Bottom status bar: Местный (with icon), Полный доступ (orange, triangle icon), ModeSelector (diamond icon), project path (crosshair icon)

### 5. Transcript Messages — ALL FLAT
- **UserMessage**: Just `py-2` + `whitespace-pre-wrap text-[13px]`, no card/bubble
- **AssistantMessage**: Flat `py-2`, Markdown rendered, copy button + "продолжай" continue button
- **ToolCard**: Codex-style file badges — "Редактирование file.ts +16 -0 ●", collapsible details
- **BashCard**: Inline collapsible, spinner while running, green checkmark when done
- **DiffCard**: Flat green checkmark + filepath + colored diff lines
- **StreamingText**: Minimal, pulsing cursor, no card wrapper
- **SystemMessage**: Centered text-[12px] text-tertiary
- **FindingCard**: Flat severity color + file + title + explanation

### 6. New Components
- **CommitDialog** (`shared/CommitDialog.tsx`): Full commit modal — branch name, file count, diff stats, "Включить неиндексированное" toggle, commit message textarea, radio actions (commit, commit+push, commit+PR, draft)
- **FileChangeSummary** (`transcript/FileChangeSummary.tsx`): "Изменено N файлов +X -Y" summary bar with individual file rows — NOT YET WIRED into transcript
- **TriadLogo** (`shared/TriadLogo.tsx`): Three teardrop petals in ChatGPT-bloom trefoil style, uses currentColor

### 7. Other Cleaned Components
- **BridgeStatusBanner**: Simplified, flat rounded-lg, Retry button
- **SidebarFooter**: Just "Настройки" button with person-circle icon
- **SessionItem**: Active state uses `bg-white/[0.06]`, running shows animated spinner
- **ProjectGroup**: Folder SVG icon, no count badge
- **TerminalDrawer**: Removed ambient effects, simple chevron toggle
- **DiffPanel**: Flat file tabs, code-centric diff view
- **TranscriptOverview**: Flat rounded-lg with text stats

## What Needs Polish (TODO for Next Agent)

### Priority 1: Visual Refinement (the "сырое" / "raw" issues)

1. **Title bar right side is cramped** — "Переместить в рабочее дерево" text gets cut off on narrow windows. Consider truncating or hiding label at small widths.

2. **Composer controls wrap on narrow windows** — "Claude Opus 4.6" + "Очень высокий" can overflow to two lines. Need `whitespace-nowrap` and `overflow-hidden` on the controls row, or hide labels below a breakpoint.

3. **Status bar spacing** — The bottom status bar items (Местный, Полный доступ, Solo, FounderOS) need consistent spacing and alignment. Compare pixel-for-pixel with Codex's status bar.

4. **Empty state positioning** — The "Давайте построим" empty state needs to be vertically centered better. Currently sits slightly high.

5. **Hover states** — Many buttons lack visible hover feedback. Codex uses subtle `bg-white/5` or `bg-white/8` on hover. Audit all interactive elements.

6. **Font weights and letter-spacing** — Codex uses very precise typography. Compare title bar text, sidebar items, and composer text sizes with Codex screenshots. Codex title bar uses ~12px for button labels.

7. **Border subtlety** — Some borders are too visible (`rgba(255,255,255,0.08)`). Codex uses extremely subtle borders — closer to `rgba(255,255,255,0.04)` in many places.

8. **Scrollbar styling** — Current scrollbar is 6px white/10%. Codex scrollbar is nearly invisible — thinner, lower opacity.

### Priority 2: Missing Features

9. **FileChangeSummary not wired** — `FileChangeSummary.tsx` exists but is NOT imported or rendered anywhere. It should appear in the transcript after a series of file-editing tool calls, showing the aggregate "Изменено N файлов" summary.

10. **CommitDialog not wired to TitleBar** — The TitleBar has a `commitOpen` state but doesn't pass it to CommitDialog. The `setCommitOpen` in TitleBar and the `commitOpen/setCommitOpen` in App.tsx are disconnected. Fix: either lift commit state to App.tsx only (it's already there) or wire TitleBar's button to App's state via a store.

11. **Task checklist in transcript** — Codex shows "0 из Выполнены 4 задачи" inline task list during runs. Not built yet.

12. **Plugins/Settings screens** — Nav items "Навыки и приложения" and "Автоматизации" are buttons that do nothing. Eventually need proper screens.

### Priority 3: Cleanup

13. **`logo-preview.html`** — Delete before committing, it's a dev preview file.

14. **Unused Badge.tsx** — The old `shared/Badge.tsx` component may still exist but is no longer imported. Verify and remove.

15. **App.tsx bg class** — Changed from `bg-surface` to `bg-[var(--color-bg-surface)]` — verify the Tailwind `bg-surface` alias still exists and works, or keep the explicit var.

16. **Console.log cleanup** — Audit for any stray `console.log` statements in modified files.

## Triad-Unique Features (Preserve These)

These are NOT in Codex and must be preserved in their Codex-like wrappers:

- **ModeSelector** (Solo/Critic/Brainstorm/Delegate) — in composer status bar with diamond icon
- **Multi-provider ModelSelector** (Claude Opus 4.6, Claude Sonnet 4.6, GPT-5.4, Gemini 2.5 Pro)
- **Access mode toggle** (Местный/Удаленный) — in composer controls
- **Reasoning effort selector** (Очень высокий/Высокий/Средний)
- **Critic/Brainstorm/Delegate RPC modes** — in Composer handleSend
- **BridgeStatusBanner** — Python backend connection status
- **TerminalDrawer** — embedded xterm.js terminal
- **DiffPanel** — side-by-side diff viewer
- **CommandPalette** — ⌘K command palette
- **Session fork/export/import** — in command palette

## Architecture Notes

- **Stores**: Zustand — `bridge-store`, `project-store`, `provider-store`, `session-store`, `ui-store`
- **RPC**: `lib/rpc.ts` — JSON-RPC bridge to Python backend via WebSocket
- **Types**: `lib/types.ts` — Message, Session, etc.
- **No CSS modules** — everything is Tailwind classes
- **React 19** — uses new features; no React.FC pattern
- **Virtual scrolling** — Transcript uses @tanstack/react-virtual for performance

## How to Verify

1. Start dev server (see above)
2. Open in Claude Preview or browser at http://127.0.0.1:1420
3. Screenshot the Codex Desktop app (installed on this Mac) for pixel comparison
4. Run `tsc --noEmit` to verify zero TypeScript errors
5. Check all interactive elements have proper hover/active states
6. Compare sidebar, title bar, composer, empty state, and transcript messages with reference screenshots in `docs/design-references/`
