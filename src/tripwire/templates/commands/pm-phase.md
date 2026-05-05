---
name: pm-phase
description: Advance project.phase through scoping → scoped → executing → reviewing.
argument-hint: "<target-phase>"
---

You are the project manager. Load the project-manager skill if not active.

$ARGUMENTS

Workflow: `phase-advancement` in `workflow.yaml`. Each phase boundary
has gate requirements enforced by the validator (`v_phase_requirements`):

- **`scoping → scoped`** — `plans/artifacts/gap-analysis.md` and
  `compliance.md` exist and carry `<!-- status: complete -->`.
- **`scoped → executing`** — every session has `plan.md`.
- **`executing → reviewing`** — every issue's `developer.md` and
  `verified.md` are present.

Procedure:

1. Read `project.yaml`, note the current `phase`.
2. Run `tripwire validate` — phase-gate findings surface here.
3. If gates fail, stop and report the missing artifacts.
4. If clean, set `phase: <target>` in `project.yaml` and re-validate.

See `references/VALIDATION.md` (`phase/*` codes) for the full gate
catalogue.
