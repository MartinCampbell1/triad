# Product Map

## Canonical Product Path

Triad desktop is the mainline product in this repository.

- `desktop/`: Tauri shell, React UI, Playwright E2E, visual regression entrypoint.
- `triad/desktop/`: Python bridge, event merger, search, terminal manager, session orchestration.
- `triad/core/`: provider adapters, execution policy, worktrees, storage, orchestration primitives.
- `.github/workflows/`: release gates for Python, frontend, smoke, and desktop E2E.

## Release Path

The production release path is:

1. `triad.desktop.bridge` starts the Python sidecar.
2. `desktop/src/lib/rpc.ts` talks only to the live bridge or an explicitly injected E2E test bridge.
3. `schemas/stream-event.schema.json` defines the canonical UI stream contract.
4. `desktop/e2e/*.spec.ts` and `scripts/desktop_smoke.py` gate the desktop release surface.

## Legacy or Historical Paths

These directories remain in the repository for compatibility or historical reference, but they are not the canonical desktop release path.

- `triad/proxy/`: legacy API proxy path.
- `triad/patcher/`: historical patching workflow.
- `triad/tui/`: earlier terminal UI.

Release gates intentionally block new imports from these legacy paths into `desktop/` and `triad/desktop/`.
