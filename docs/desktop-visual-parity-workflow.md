# Desktop Visual Parity Workflow

This document defines the canonical screenshot-driven review loop for the desktop shell.

The goal is not to create ad hoc screenshots during implementation. The goal is to produce a fixed, repeatable screenshot pack that can be used to compare layout, typography, spacing, and dev-noise exposure against the Codex reference set.

## Canonical pack

- Use a fixed viewport: `1440x920`.
- Capture the desktop shell in dark mode unless a task explicitly requires a different theme.
- Capture screenshots from the browser-rendered desktop shell, not from ad hoc crop tools.
- Store outputs under `desktop/visual-parity/`.
- Keep one manifest per pack run so the output can be audited later.

Current starter pack:

- `desktop-shell` - the default desktop shell at `/`.

## Run workflow

1. Start the desktop dev server from the `desktop/` workspace.
2. Wait until the shell is reachable at `http://127.0.0.1:1420`.
3. Run the screenshot pack:

```bash
pnpm --dir desktop visual:pack
```

4. Open the generated PNGs in `desktop/visual-parity/`.
5. Compare them against the current reference pack and note any drift.

## Visual review checklist

- Window chrome is aligned with the intended shell density.
- Sidebar width, truncation, and active-state contrast match the reference.
- Secondary surfaces do not expose raw runtime noise, paths, or debug-only labels unless explicitly needed.
- Typography uses the intended hierarchy and does not collapse into generic defaults.
- Spacing is consistent across title bar, sidebar, composer, and content surfaces.
- Empty states, loading states, and error states are visually intentional.
- The screenshot is stable across repeated runs with the same viewport.

## Output contract

- Every pack run writes PNG screenshots into `desktop/visual-parity/`.
- Every pack run writes a `manifest.json` with the resolved base URL, viewport, and capture list.
- If a pack is updated, note the reason in the PR or audit log.

## Baseline guidance

- Prefer one canonical capture per shell surface until a surface has a stable review target.
- Add more targets only when the viewport and state are reproducible without manual clicking.
- If a screen needs manual setup before capture, document the steps next to the target definition.

## Notes

- The runner is intentionally minimal. It is a capture scaffold, not a visual diff engine.
- If a future audit needs pixel-diff enforcement, add that as a separate step rather than complicating the baseline capture command.
