---
name: pm-handoff
description: Create a session for an issue and hand it off to a coding agent.
argument-hint: "<issue-key> [agent-type]"
---

You are the project manager for this repository. Load the project-manager
skill if not active.

Handoff request:
$ARGUMENTS

Workflow:

1. Parse the arguments. The first token is the issue key (e.g. `MP-42`).
   The optional second token is the agent type (e.g. `backend-coder`,
   `frontend-coder`, `verifier`). If the agent type is missing, infer
   from the issue's `agent` field or its labels.
2. Run `keel brief` to load the project state.
3. Read the issue file at `issues/<issue-key>.yaml`.
4. Verify the issue is ready to hand off:
   - Status should be `todo` or `ready` (not already in progress).
   - All `blocked_by` dependencies are done.
   - All referenced concept nodes exist and are fresh.
   - If the issue is not ready, report why and stop.
5. Allocate a new session key via `keel next-key --type session` (if
   session keys are sequential in this project) or generate a slug.
6. Create the session directory at `sessions/<session-key>/` with:
   - `session.yaml` (uses the template in `session_templates/`)
   - `plan.md` (from `templates/artifacts/plan.md.j2`)
   - `task-checklist.md` (from the template)
   - `verification-checklist.md` (from the template)
7. Fill the templates with content specific to this issue (what to do,
   why, acceptance criteria, testing plan).
8. Update the issue status to `in_progress` and add a comment linking
   to the new session.
9. Run `keel validate --strict`. Fix any errors.
10. Commit with a message like `handoff: <issue-key> → <agent-type>`.
11. Report the session directory path so the user (or the orchestration
    runtime) can dispatch the coding agent.

Full dispatch to a containerised agent runtime is out of scope for v0.
This command produces the session files; the runtime (see
`docs/agent-containers.md`) handles the actual agent spawn later.
