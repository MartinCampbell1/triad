# ADR-000: Mainline Product Surface

## Status

Accepted

## Date

2026-04-06

## Context

Triad currently contains several historical product paths:

- `desktop/` for the Tauri desktop shell
- `triad/desktop/` for the Python bridge and desktop runtime
- `triad/core/` for shared orchestration, providers, storage, and policies
- `triad/proxy/`, `triad/patcher/`, and `triad/tui/` as older or experimental paths

This made it unclear which surface is the real product, which paths are legacy, and which modules are safe to extend for current work.

## Decision

The mainline Triad product is:

- `desktop/` as the only supported user-facing client
- `triad/desktop/` as the only supported desktop bridge/runtime host
- `triad/core/` as the shared domain layer for orchestration, providers, storage, worktrees, and policy

The following paths are not mainline and must not define product direction for the desktop app:

- `triad/proxy/`: legacy or experimental integration path
- `triad/patcher/`: archived compatibility path
- `triad/tui/`: deprecated standalone interface, maintained only as historical reference unless explicitly revived

## Consequences

- New desktop product work should land in `desktop/`, `triad/desktop/`, or `triad/core/`.
- Production behavior must be designed around the desktop bridge contract, not proxy or patcher fallbacks.
- Legacy paths may still be referenced for migrations, tests, or archaeology, but they are not the source of truth.
- Future cleanup can move legacy paths into an `archive/` area or separate repository without changing the current product contract.
