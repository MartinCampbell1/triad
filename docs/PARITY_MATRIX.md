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
