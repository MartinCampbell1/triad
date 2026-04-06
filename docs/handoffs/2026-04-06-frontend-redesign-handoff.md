# Triad Desktop Frontend Redesign Handoff

**Date:** 2026-04-06  
**Branch:** `codex/ship-triad-desktop-client`  
**Latest commit:** `9c22f7a`  
**Purpose:** handoff for a frontend-focused rewrite/polish pass to get the UI much closer to the Codex Desktop references.

## 1. What the user actually wanted

The requirement was not "a dark desktop chat app in the same category". The requirement was:

- 95% visual fidelity to Codex Desktop
- same shell structure and density
- same overall layout rhythm
- same sidebar behavior and visual hierarchy
- same title bar / chrome feel
- same transcript look for tool-heavy coding sessions
- same composer feel and control density
- same terminal drawer / diff panel / split-view feeling

The references are the source of truth. The current frontend implementation is **functionally useful**, but it is **not visually close enough** and should be treated as a scaffold, not as final UI.

## 2. Source of truth

Use these files first. Do not start by trusting the current JSX/CSS.

### Visual source of truth

- `docs/design-references/CATALOG.md`
- `docs/design-references/`

`CATALOG.md` maps each screenshot to the screen it represents. The actual PNGs are stored in `docs/design-references/` with filenames like:

- `Снимок экрана 2026-04-06 в 02.01.54.png`
- `Снимок экрана 2026-04-06 в 02.02.03.png`
- `Снимок экрана 2026-04-06 в 02.03.42.png`
- `Снимок экрана 2026-04-06 в 02.05.01.png`

### Design token / system source of truth

- `docs/design-tokens.json`
- `docs/DESIGN_SYSTEM.md`

These contain extracted Codex colors, typography, spacing, radii, dark theme semantics, and layout guidance.

### Product / architecture source of truth

- `docs/superpowers/specs/2026-04-06-triad-desktop-client-design.md`
- `docs/superpowers/plans/2026-04-06-triad-desktop-client.md`

The spec explains what the desktop app is supposed to be. The plan shows the intended component structure and feature slices.

## 3. The most important reference screens

If time is limited, match these first, in this order:

1. `02.01.54` — main chat with sidebar, transcript, composer, terminal drawer
2. `02.02.03` — new chat / empty state
3. `02.03.42` — active coding session with terminal
4. `02.03.48` — tool execution / file-analysis transcript feel
5. `02.05.01` — split view: chat + code preview
6. `02.05.17` — split view: diff state
7. `02.05.30` — commit dialog
8. `02.03.55` / `02.04.01` / `02.04.04` / `02.04.10` / `02.04.16` — sidebar density, badges, footer accounts/settings

## 4. Current codebase status

### Runtime / backend status

The backend side is in usable shape. The desktop runtime, JSON-RPC bridge, session orchestration, terminal, search, import/export, fork, file watcher, diagnostics and persistence are implemented and validated. The frontend redesign should try hard **not** to break these contracts.

Relevant runtime files:

```text
triad/desktop/bridge.py
triad/desktop/orchestrator.py
triad/desktop/claude_pty.py
triad/desktop/file_watcher.py
triad/desktop/event_merger.py
triad/desktop/terminal_manager.py
triad/desktop/search.py
```

### Frontend status

The desktop shell exists and is wired, but the visual result is not close enough to the references.

Main frontend entry points:

```text
desktop/src/App.tsx
desktop/src/lib/rpc.ts
desktop/src/lib/types.ts
desktop/src/stores/session-store.ts
desktop/src/stores/project-store.ts
desktop/src/stores/provider-store.ts
desktop/src/stores/ui-store.ts
desktop/src/styles/tokens.css
desktop/src/styles/globals.css
```

Main visual component files:

```text
desktop/src/components/sidebar/Sidebar.tsx
desktop/src/components/sidebar/ProjectGroup.tsx
desktop/src/components/sidebar/SessionItem.tsx
desktop/src/components/sidebar/SearchPanel.tsx
desktop/src/components/sidebar/SidebarFooter.tsx

desktop/src/components/layout/TitleBar.tsx

desktop/src/components/transcript/Transcript.tsx
desktop/src/components/transcript/AssistantMessage.tsx
desktop/src/components/transcript/UserMessage.tsx
desktop/src/components/transcript/ToolCard.tsx
desktop/src/components/transcript/DiffCard.tsx
desktop/src/components/transcript/BashCard.tsx
desktop/src/components/transcript/FindingCard.tsx
desktop/src/components/transcript/StreamingText.tsx
desktop/src/components/transcript/SystemMessage.tsx
desktop/src/components/transcript/TranscriptOverview.tsx

desktop/src/components/composer/Composer.tsx
desktop/src/components/composer/ModelSelector.tsx
desktop/src/components/composer/ModeSelector.tsx

desktop/src/components/terminal/TerminalDrawer.tsx
desktop/src/components/diff/DiffPanel.tsx

desktop/src/components/shared/Badge.tsx
desktop/src/components/shared/BridgeStatusBanner.tsx
desktop/src/components/shared/CommandPalette.tsx
desktop/src/components/shared/DiagnosticsPanel.tsx
```

## 5. Current frontend problems

This is the actual handoff-critical part.

### Problem summary

The current implementation works as an interaction scaffold but misses the Codex visual target in several ways:

- title bar chrome is too custom and too noisy
- sidebar density, rhythm, typography and badges do not match the reference closely enough
- transcript cards and message treatment feel too component-library-ish instead of Codex-native
- composer is structurally similar but visually off in spacing, height, button sizing and control balance
- split/diff side does not yet feel like the real Codex editor/diff surface
- some “extra runtime chrome” appears too prominently in states where Codex would stay quieter
- overall micro-spacing and alignment are inconsistent with the references

### Treat these as likely redesign targets

- `desktop/src/components/layout/TitleBar.tsx`
- `desktop/src/components/sidebar/*`
- `desktop/src/components/composer/*`
- `desktop/src/components/transcript/*`
- `desktop/src/components/diff/DiffPanel.tsx`
- `desktop/src/components/terminal/TerminalDrawer.tsx`
- `desktop/src/styles/tokens.css`
- `desktop/src/styles/globals.css`

### Specific mismatch notes

- The app should feel flatter, tighter, quieter and more “native” than it currently does.
- Avoid inventing decorative gradients, pills and callout surfaces unless they are directly visible in the references.
- Badge usage should be reduced and made subtler.
- Sidebar rows need closer matching to Codex row height, text size, count badge style, and hover/active states.
- Composer controls should read as compact system controls, not large custom chips.
- Transcript body should feel more like full-width content on a dark document surface, not a gallery of boxed cards.
- The right-hand split view needs to look like a real code pane, not a generic panel.
- The terminal drawer should feel like a true embedded IDE terminal, with matching tab/header treatment.

## 6. What is already safe to keep

The following areas are more about behavior than visual identity and can usually be preserved while redesigning:

- Zustand stores in `desktop/src/stores/`
- RPC integration in `desktop/src/lib/rpc.ts`
- type contracts in `desktop/src/lib/types.ts`
- run streaming and event handling in `desktop/src/hooks/useStreamEvents.ts`
- keyboard shortcuts in `desktop/src/hooks/useKeyboardShortcuts.ts`
- Tauri macOS integration in `desktop/src/lib/tauri-macos.ts`

In other words: prefer rewriting visual components and CSS over rewriting runtime state plumbing.

## 7. What is missing or still rough from a frontend-product perspective

These areas are either absent, incomplete, or not yet visually production-grade:

- plugin marketplace and plugin management screens from the references
- high-fidelity commit dialog matching `02.05.30`
- truly Codex-like split diff/editor experience
- more exact sidebar footer / account / settings area
- exact title bar actions and right-side usage/account affordances
- refined happy-path state where diagnostics / fallback messaging are visually minimized

## 8. Recommended redesign approach

Do this in this order to maximize speed and avoid breaking runtime:

1. Lock the base shell.
2. Match the main chat screen to `02.01.54`.
3. Match the empty state to `02.02.03`.
4. Match active coding transcript states to `02.03.42`, `02.03.48`, `02.04.37`, `02.04.43`.
5. Match split view to `02.05.01` and `02.05.17`.
6. Build commit dialog to match `02.05.30`.
7. Only after that, work on secondary screens like plugins/manage/settings/users.

Practical rule: **screenshots first, components second**.

## 9. Concrete implementation guidance

### Sidebar

Target files:

```text
desktop/src/components/sidebar/Sidebar.tsx
desktop/src/components/sidebar/ProjectGroup.tsx
desktop/src/components/sidebar/SessionItem.tsx
desktop/src/components/sidebar/SearchPanel.tsx
desktop/src/components/sidebar/SidebarFooter.tsx
```

What to fix:

- exact width and padding rhythm
- row heights
- label sizing
- message count badge treatment
- group disclosure affordances
- bottom user/settings area

### Title bar

Target file:

```text
desktop/src/components/layout/TitleBar.tsx
```

What to fix:

- overall density
- spacing between traffic lights, nav arrows, title, actions
- make it feel much closer to Codex chrome
- reduce the feeling of “custom toolbar”

### Transcript

Target files:

```text
desktop/src/components/transcript/Transcript.tsx
desktop/src/components/transcript/AssistantMessage.tsx
desktop/src/components/transcript/UserMessage.tsx
desktop/src/components/transcript/ToolCard.tsx
desktop/src/components/transcript/DiffCard.tsx
desktop/src/components/transcript/BashCard.tsx
desktop/src/components/transcript/FindingCard.tsx
desktop/src/components/transcript/StreamingText.tsx
desktop/src/components/transcript/SystemMessage.tsx
```

What to fix:

- flatten the presentation
- make spacing more editorial and less widget-like
- align code/tool blocks with Codex density
- match file analysis / tool-run transcript tone from the references

### Composer

Target files:

```text
desktop/src/components/composer/Composer.tsx
desktop/src/components/composer/ModelSelector.tsx
desktop/src/components/composer/ModeSelector.tsx
```

What to fix:

- control sizes and border treatment
- send button shape/weight
- bottom metadata row
- exact visual priority of model selector, reasoning selector and permission/access indicators

### Diff / terminal

Target files:

```text
desktop/src/components/diff/DiffPanel.tsx
desktop/src/components/terminal/TerminalDrawer.tsx
```

What to fix:

- make split/editor panel feel real and code-centric
- make terminal header and panel proportions closer to Codex
- make unstaged/diff surfaces much more faithful to `02.05.01` and `02.05.17`

## 10. Styling notes to keep in mind

Use `docs/DESIGN_SYSTEM.md` and `docs/design-tokens.json`, but apply them with judgment:

- default UI text is around `13px`
- main dark surface is around `#181818`
- elevated dark surface is around `#282828`
- primary blue accent is around `#339cff`
- borders are very soft and low-contrast
- system font stack is the right direction
- most of Codex’s feel comes from spacing and restraint, not from decorative effects

Important: if a token choice conflicts with the screenshot, prefer the screenshot.

## 11. Run / test commands

### Frontend dev

```bash
cd /Users/martin/triad/desktop
corepack pnpm dev --host 127.0.0.1 --port 1420
```

### Frontend production build

```bash
cd /Users/martin/triad/desktop
corepack pnpm typecheck
corepack pnpm build
```

### Tauri desktop dev

```bash
cd /Users/martin/triad/desktop
corepack pnpm tauri dev
```

### Tauri production build

```bash
cd /Users/martin/triad/desktop
corepack pnpm tauri build
```

Current packaging note:

- `.app` build succeeded
- `.dmg` packaging failed at the final bundling stage
- built app bundle exists at `desktop/src-tauri/target/release/bundle/macos/Triad.app`

## 12. Final guidance for the next frontend person

- Do not spend time re-architecting the runtime.
- Do not start by polishing the current visual language.
- Start from the screenshots and re-skin / re-layout aggressively where needed.
- Preserve the current data flow and event plumbing unless a screen absolutely requires structural changes.
- If there is a conflict between “looks close to Codex” and “keeps current component abstractions tidy”, pick Codex fidelity.

That is the actual user expectation for this handoff.
