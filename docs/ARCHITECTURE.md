# Architecture

## Mainline Layers

1. `desktop/`
   React/Tauri shell, recovery UI, transcript, diff surface, terminal drawer, Playwright E2E harness.

2. `triad/desktop/`
   JSON-RPC bridge, session runtime, file watcher, event merger, diagnostics, terminal manager, search, session transfer.

3. `triad/core/`
   Provider adapters, execution policy, account pools, worktrees, storage.

## Authoritative Event Path

1. `schemas/stream-event.schema.json` defines canonical event names, aliases and required fields.
2. `triad/desktop/event_schema.py` normalizes and validates Python emitters against that schema.
3. `desktop/src/lib/stream-event-contract.ts` is generated from the same schema for frontend consumers.
4. `desktop/src/lib/rpc.ts` hydrates incoming JSON-RPC notifications into typed frontend events.

## Release Boundaries

- The desktop product must fail closed when the bridge is unavailable.
- Mock backend state is not allowed in the canonical runtime path.
- Legacy `proxy`, `patcher`, and `tui` modules must not be imported from `desktop/` or `triad/desktop/`.
