# Parity Matrix

Reference screenshots live in `docs/design-references/`.

| Screen | Current Triad Surface | Reference Screenshot | Owner | Status |
|---|---|---|---|---|
| Empty state | No active session in `Transcript` | `02.02.03.png` | desktop-shell | In progress |
| Active session shell | Main shell with transcript + composer | `02.01.54.png` | desktop-shell | In progress |
| Tool card | `ToolCard` transcript surface | `02.03.48.png` | transcript | In progress |
| Diff card | `DiffCard` transcript surface | `02.05.17.png` | transcript | In progress |
| Terminal drawer open | `TerminalDrawer` expanded | `02.03.42.png` | terminal | In progress |
| Recovery state | `RecoveryScreen` fail-closed path | `02.02.03.png` nearest shell baseline | recovery | New |
| Project unavailable | `RecoveryScreen` project chooser | `02.02.03.png` nearest shell baseline | recovery | New |
| Commit / export affordances | command palette + export flows | `02.05.30.png` | workflow | Planned |

## Visual Regression Policy

- `desktop/e2e/*@visual` tests are the executable screenshot baseline.
- Screenshots are regenerated only for intentional UI changes.
- Any parity work should update this matrix with the exact reference screenshot before merging.

## Acceptance Checklist

- Empty state spacing matches the reference shell rhythm.
- Active session shell keeps composer and transcript density within the current baseline budget.
- Tool and diff cards remain legible at desktop and laptop widths.
- Recovery states preserve the same chrome hierarchy as the main shell.
- Terminal open/close does not reflow the sidebar or titlebar unexpectedly.

## Review Rubric

| Category | Target |
|---|---|
| Layout density | Within one spacing step of the reference shell |
| Typography tension | No more than one weight/size step from the reference hierarchy |
| Radius/shadow | Same component family across shell, recovery and transcript cards |
| Motion | No gratuitous animation on transcript, recovery or terminal transitions |
