---
name: pm-monitor
description: Run one tick of the pm-monitor scan/classify/dispatch loop.
argument-hint: "[--once] [--dry-run]"
---

You are the project manager. Load the project-manager skill if not active.

$ARGUMENTS

Workflow: `pm-monitor` in `workflow.yaml` (`scan → classify → dispatch →
idle → scan`). One invocation = one tick. The scan walks `sessions/`,
inbox, comments, and node freshness to emit signals; classify routes
each signal; dispatch fires the matching cross-link.

Reference: `references/MONITOR_CRITERIA.md` for the signal vocabulary
and threshold configuration.

`--once` runs a single tick and exits (default). Long-running monitor
mode is owned by the runtime, not this command — see
`/pm-session-monitor` for self-paced session monitoring.
