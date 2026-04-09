# Release Process

## Blocking Checks

1. `python-ci.yml`
2. `frontend-ci.yml`
3. `desktop-smoke.yml`
4. `desktop-e2e.yml`
5. `release-gates.yml`

## Desktop Release Definition of Done

- Bridge boots without mock fallback.
- Recovery flow is available for bridge and project failures.
- Stream events validate against `schemas/stream-event.schema.json`.
- Golden stream traces cover solo, critic, diff, finding, stderr and interruption scenarios.
- Visual baselines pass for recovery and shell screens.

## Pre-release Checklist

- Update `docs/PARITY_MATRIX.md` for any intentional UI change.
- Regenerate `desktop/src/lib/stream-event-contract.ts` if the schema changes.
- Run `python3 scripts/release_gates.py` and `python3 scripts/desktop_smoke.py` locally.
