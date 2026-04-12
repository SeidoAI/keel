---
name: pm-update
description: Apply a surgical update to an existing project (status change, new node, comment).
argument-hint: "<free-text change description>"
---

You are the project manager for this repository. Load the project-manager
skill from `.claude/skills/project-manager/SKILL.md` if not active, then
execute the **Incremental Update** workflow in
`.claude/skills/project-manager/references/WORKFLOWS_INCREMENTAL_UPDATE.md`.

Change requested:
$ARGUMENTS

Before editing any files:

1. Run `keel brief` to load current project state if you haven't already.
2. Parse the user's change description to identify the target entities
   (issue key, session, node ID) and the action (status change, add
   comment, create node, update session).
3. Read the target entity file(s) to confirm current state.
4. Apply the minimal set of edits needed to execute the change.
5. If the change affects the concept graph (new `[[node]]` references,
   or a new node file), verify the graph is consistent.
6. Run `keel validate --strict`. Fix any errors.
7. When validation is clean, commit the result with a focused message
   describing just this change.

Do not expand the scope beyond what the user asked for. Incremental
updates stay surgical.
