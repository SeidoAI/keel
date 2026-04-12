# Workflow: Initial Scoping

The workflow for transforming raw planning documents into a fully scoped
project. You have planning docs and need to emit a coherent set of
issues, concept nodes, and sessions that pass validate — complete with
session plans ready for delegation to execution agents.

## Precondition

You are in a freshly-init'd `keel` directory. `keel init` creates an
empty `./plans/` subdirectory by default — the user drops raw planning
docs in there before invoking scoping. Scoping also works from user
intent alone if `./plans/` is empty or missing.

## Before you start

**Do not set a target number of issues, nodes, or sessions.** Let the
planning docs dictate the count. If you find yourself thinking "that's
enough issues," that's a red flag — the planning docs, not your
intuition, define scope. You are not constrained by time the way a
human is. Writing 40 issues takes you minutes, not days. Do not
compress scope to save effort.

## Procedure

### 1. Front-load context
```bash
keel brief
```
Read the output. Note the `next issue key`, active enums, registered
repos, artifact manifest, orchestration pattern, and skill example
paths.

**Repos:** If the planning docs reference repositories not registered
in `project.yaml`, register them now. Edit `project.yaml` and add
each repo under `repos:` with its GitHub slug and optional local
clone path. Every issue must reference a registered repo.

### 2. Read the planning docs

Read every `.md` file under `./plans/` in full — you cannot scope
what you haven't read. If `./plans/` is empty or missing, use the
user's intent (passed via `$ARGUMENTS` to `/pm-scope`) as your sole
source and proceed.

**If a file exceeds your read limit:** read it in chunks. Do NOT skip
sections. Read every section of every file — you cannot scope what you
haven't read. Skimming for gist is not reading. You need every
endpoint table, every schema definition, every infra resource, every
migration step.

### 3. Read the canonical examples

Before writing any file, read at least:
- `examples/issue-fully-formed.yaml`
- `examples/issue-epic.yaml`
- `examples/node-endpoint.yaml`
- `examples/node-decision.yaml`
- `examples/session-planned.yaml`
- `examples/artifacts/plan.md`

The example files are the canonical truth. If your output doesn't look
like them, you're doing it wrong.

### 4. Write the scoping plan artifact

**This step produces a file, not a mental sketch.** Write:

```
plans/artifacts/scoping-plan.md
```

Structure:
```markdown
# Scoping plan

## Epics
- Epic 1: [title] — [one-sentence scope]
- Epic 2: ...

## Issues
For each issue:
- [title] — parent: [epic], repo: [slug], executor: [ai|human],
  priority: [H/M/L], blocked_by: [list], concept refs: [node-ids]

## Concept nodes
For each node:
- [slug-id] — type: [endpoint|model|config|decision|contract|...],
  referenced by: [issue list]

## Sessions
For each session:
- [slug-id] — issues: [list], blocked_by_sessions: [list],
  estimated_size: [S/M/L]
```

**This file is consumed by step 5.** If it doesn't exist, step 5
cannot proceed.

### 5. Allocate IDs and UUIDs

Read `plans/artifacts/scoping-plan.md`. For each issue listed:
```bash
keel next-key --type issue --count N
```
where N is the number of issues. Collect the allocated keys.

For UUIDs:
```bash
keel uuid --count N
```
where N is the total entity count (issues + nodes + sessions). Save
the output. Assign UUIDs to entities from this list as you write
files. Do NOT hand-craft UUIDs.

Node and session ids are slugs you choose (lowercase, letter-first,
hyphenated). Session ids should be descriptive: `storage-adapter-impl`,
`api-endpoints-core`, `frontend-shell`.

### 6. Write the files

Write in dependency order so early files can be referenced by later
ones:

1. **Concept nodes first** → `graph/nodes/<id>.yaml`
2. **Epic issues** → `issues/<KEY>.yaml` (parent: null, no repo)
3. **Concrete issues** → `issues/<KEY>.yaml`. Reference epics as
   `parent`, reference concept nodes via `[[node-id]]` in the body.
4. **Sessions** → `sessions/<id>/session.yaml` (directory, not flat
   file). Each session gets its own directory.
5. **Session plans** → `sessions/<id>/plan.md` for every session,
   using the step-by-step template from `examples/artifacts/plan.md`.

**Issue depth:** Every issue will be read by an execution agent that
has NOT read the planning docs and does NOT share your context.
Default to more detail, not less. If a concept, endpoint, schema, or
decision is relevant to the issue, write it into the issue body
explicitly. The execution agent cannot infer what you know.

**Forward references:** Dangling `[[node-id]]` refs are always wrong —
create the node first, then the referrer. Dangling `blocked_by` refs
to issues you've allocated keys for but haven't written yet are
acceptable — they resolve when you write those issues in the next
batch.

### 7. Red-green validation cycle

After every 3-5 files:
```bash
keel validate --strict
```

The output is JSON by default. Errors are grouped by category. Walk
them in order:

1. **`schema/*`**: fill in placeholder fields with real values
2. **`ref/dangling`**: create the target node or replace the
   placeholder ref
3. **`body/*`**: fill in missing body sections
4. **`enum/*`**: fix invalid enum values
5. **`coverage/*`**: investigate — these are warnings about potential
   semantic gaps (no node refs in an issue, under-referenced nodes)

Repeat until `exit_code == 0`.

**What validate checks and doesn't check:** `keel validate` checks
structural integrity — schemas, references, bidirectional consistency,
status transitions, freshness, UUID format. It does NOT check semantic
completeness. A clean validate means structurally sound, not "the
scope is complete." The gap analysis step (step 9) is where you check
completeness.

### 8. Second-pass: node coverage

After all issues are written and validate is green, scan every issue
body:

- Any concept mentioned in prose (not as a `[[ref]]`) in 3+ issues?
  → Create a node for it and replace the prose with `[[ref]]` syntax.
- Any `[[node-id]]` referenced by only 1 issue? → Either the node is
  too narrow (merge it) or other issues forgot to reference it
  (add refs).
- Any issue with zero `[[node-id]]` references in its body? → The
  issue isn't linked to the concept graph. Add references.

Run `keel refs summary` to see reference counts across all nodes.

### 9. Gap analysis

Produce `plans/artifacts/gap-analysis.md`:

**Planning doc → project coherence:**
Reread every planning doc. For each section, list every concrete
deliverable (endpoint, migration, UI page, infra resource, CI/CD
pipeline, schema change). Check: does an issue cover this? If not,
flag as **GAP** and create the missing issue.

**Planning doc internal coherence:**
Do the planning docs contradict each other? Does the API spec
reference infra the infra spec doesn't mention? Does the frontend
depend on endpoints the API spec doesn't list? Flag as
**INCONSISTENCY** and create a comment on the relevant issue.

**Project self-coherence:**
Run `keel agenda` and `keel graph --type concept`. Check:
- Any issues with 0 concept node refs? Flag.
- Any nodes with only 1 referrer? Flag.
- Any sessions with 0 issues? Flag.
- Does the dependency graph make sense? Cycles? Orphans?

For each gap: create the missing issue or node. For each
inconsistency: create a comment on the relevant issue.

### 10. Produce meta-artifacts

Write three artifacts in `plans/artifacts/`:

1. **`scoping-verification.md`** — maps planning doc sections →
   issues/nodes. Every section must have a mapping or explicit "out
   of scope" justification.

2. **`task-checklist.md`** — your own PM task checklist tracking what
   you did: docs read, nodes created, issues created, sessions
   created, gap analysis completed.

3. **`compliance.md`** — mark each workflow rule as followed or
   deviated. If deviated, explain why.

### 11. Final validation + confirm shape
```bash
keel validate --strict
keel status
keel agenda --by status
keel graph --type concept
keel refs summary
```
All clean. Counts match your scoping plan. No orphan nodes.

### 12. Commit

**Before committing:** read `plans/artifacts/compliance.md`. If any
rule is marked "deviated," resolve it or document the justification.
Do not commit with unresolved deviations.

Per `COMMIT_CONVENTIONS.md`. One commit for the whole initial scoping.

## Anti-patterns to avoid

- Writing files before reading ALL planning docs and ALL examples.
- Skimming planning docs for gist instead of reading every section.
- Setting a target issue count before reading the docs.
- Compressing scope to save effort ("with more time I would split
  this" — split it now).
- Writing issues that assume the executor shares your context (the
  executor has NOT read the planning docs).
- Writing sessions as flat files instead of directories.
- Skipping session plans ("I'll write them later").
- Omitting repo fields from issues because repos aren't registered
  (register them first).
- Hand-crafting UUIDs instead of using `keel uuid`.
- Treating validate-green as "done" (it checks structure, not
  completeness).

## Red flags — scoping-specific rationalizations

| Agent thought | Reality |
|---|---|
| "That's enough issues for this project" | The planning docs define scope, not your intuition. Reread them and check. |
| "I'll create all the issues first and validate at the end" | Validate after every batch of 3-5 files. Errors compound. |
| "This concept doesn't need a node — it's obvious" | If 2+ issues reference it, or it's a contract/interface, it needs a node. When in doubt, create it. |
| "I'll write the plan later — let me get the issues down first" | The plan artifact is consumed by step 5. It must exist first. |
| "The planning docs are ambiguous so I'll make my best guess" | Stop. Ask the user. A wrong assumption cascades into every issue. |
| "I'll skip the gap analysis — validate passed" | Validate checks structure. Gap analysis checks completeness. Both are required. |
| "I can track UUIDs in my head if I make them predictable" | Use `keel uuid`. Hand-crafted UUIDs will be caught by the validator. |
| "With more time I would split this issue" | You have the time. Split it now. |
| "The execution agent will figure out the details" | No. The execution agent has no context you don't write down. Be explicit. |

## See also

- `CONCEPT_GRAPH.md` for the when-to-create-a-node rule.
- `VALIDATION.md` for interpreting validator errors.
- `ANTI_PATTERNS.md` for the full list of things to avoid.
- `WORKFLOWS_INCREMENTAL_UPDATE.md` for small surgical edits later.
