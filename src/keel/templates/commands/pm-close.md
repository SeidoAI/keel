---
name: pm-close
description: Mark an issue done and write a closing comment.
argument-hint: "<issue-key> [closing-note]"
---

You are the project manager for this repository. Load the project-manager
skill if not active.

Close request:
$ARGUMENTS

Workflow:

1. Parse the arguments. First token is the issue key. The rest (if any)
   is a closing note to include in the completion comment.
2. Run `keel brief` to load project state.
3. Read `issues/<issue-key>.yaml`. Verify:
   - Status is not already `done` or `canceled` (if so, report and stop).
   - If there's an associated session, check that all required artifacts
     are present (plan, task-checklist, verification-checklist,
     recommended-testing-plan, post-completion-comments).
4. Update the issue:
   - Status → `done`
   - `updated_at` → current timestamp
5. Create a completion comment using `comment_templates/completion.yaml.j2`:
   - `type: completion`
   - `author: pm-agent`
   - Body = the closing note from $ARGUMENTS, or a default if none given
6. Write the comment file to the issue's comments directory.
7. Run `keel validate --strict`. Fix any errors.
8. Commit with a message like `close: <issue-key>`.

If the issue has downstream consumers (`blocked_by` from other issues),
mention them in the closing comment so the next agent knows they're
unblocked.
