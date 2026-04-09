# Error State Matrix

| Category | User Surface | Recover Action | Telemetry Tag | Severity |
|---|---|---|---|---|
| Bridge startup failed | `RecoveryScreen` | Retry bridge | `bridge.start_failed` | fatal |
| Bridge exited during session | `RecoveryScreen` after live shell | Retry bridge | `bridge.exited` | fatal |
| Project unavailable | `RecoveryScreen` chooser | Choose project | `project.unavailable` | degraded |
| Provider execution error | Transcript system card + failed run | Retry prompt / switch provider | `provider.run_failed` | degraded |
| Critic worktree failure | Transcript failed run | Retry critic session | `critic.worktree_failed` | scoped-fatal |
| Terminal launch failure | Drawer stays closed, diagnostics path available | Retry terminal | `terminal.launch_failed` | degraded |
| Diagnostics export failure | Browser download failure | Retry export | `diagnostics.export_failed` | degraded |
| Archive import invalid | RPC error surfaced to user | Retry with valid archive | `session.import_invalid` | scoped-fatal |

## Policy

- Fatal desktop failures must never fall back to seeded mock state.
- Recovery actions must remain available even when no project or session is active.
- Every new degraded state should be mapped into this table before release.
