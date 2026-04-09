# Triad

Triad desktop is the canonical product in this repository.

## Mainline

- `desktop/`: desktop shell, transcript UI, recovery flow, Playwright E2E.
- `triad/desktop/`: Python bridge, runtime services, terminals, search, session orchestration.
- `triad/core/`: provider adapters, execution policy, worktree/runtime primitives.

## Release Gates

- `python-ci.yml`
- `frontend-ci.yml`
- `desktop-smoke.yml`
- `desktop-e2e.yml`
- `release-gates.yml`

## Legacy Paths

These remain only as historical or compatibility surfaces and are not the desktop release path:

- `triad/proxy/`
- `triad/patcher/`
- `triad/tui/`

See `docs/PRODUCT_MAP.md` for the product-line map and `docs/PARITY_MATRIX.md` for screen parity tracking.
