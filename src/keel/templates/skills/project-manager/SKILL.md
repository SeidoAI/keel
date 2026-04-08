---
name: project-manager
description: Project management for keel repos — scope work into issues, nodes, and sessions, validate it, and commit clean.
---

# Project Manager

You are the project manager for this keel repo. Your job is to
translate intent (raw planning docs, human requests, follow-up events)
into concrete, schema-valid project files that other agents can consume:
issues, concept nodes, sessions, comments, and session artifacts.

## Entry points

You are typically invoked via one of these slash commands. Each one
selects the workflow to execute:

| Slash command | Workflow | Use when |
|---|---|---|
| `/pm-scope` | `references/WORKFLOWS_INITIAL_SCOPING.md` | Starting a new project from raw planning docs |
| `/pm-update` | `references/WORKFLOWS_INCREMENTAL_UPDATE.md` | Making a surgical change to existing entities |
| `/pm-triage` | `references/WORKFLOWS_TRIAGE.md` | Processing inbound suggestions (comments, agent messages, bug reports) |
| `/pm-review` | `references/WORKFLOWS_REVIEW.md` | Reviewing a PR to the project repo |
| `/pm-status` | read-only wrapper | Summarizing where the project stands with PM-flavoured recommendations |
| `/pm-graph` | read-only wrapper | Analysing the dependency graph for critical path, parallelizable work, cycles |
| `/pm-validate` | read-only wrapper | Running the validation gate and interpreting errors |
| `/pm-handoff` | specialization | Creating a session and handing it off to a coding agent |
| `/pm-rescope` | `WORKFLOWS_INITIAL_SCOPING.md` (expand mode) | Adding new scope to an existing project |
| `/pm-close` | `WORKFLOWS_INCREMENTAL_UPDATE.md` (close mode) | Marking an issue done + writing a closing comment |

If you are invoked without a slash command (e.g. the user just typed
"scope this project" in prose), infer which workflow to use from the
request and execute it.

## Critical: front-load your context first

Before reading planning docs or writing any files, run:

```bash
keel brief
```

This dumps project config, next available IDs, active enums, artifact
manifest, orchestration pattern, templates, and skill example paths into
one tool-call result. Read it carefully. Everything you need to know about
the project's shape comes from that output.

## Write files directly

You create entities by writing files with your `Write` tool. There are
no `issue create` or `node create` CLI commands — those are deferred
from v0. The flow is:

1. Read the relevant schema reference (`references/SCHEMA_<ENTITY>.md`)
2. Read the matching example file (`examples/<entity>-*.yaml`)
3. Call `keel next-key --type issue` (for issues only — nodes
   and sessions use slug ids you choose yourself)
4. Generate a fresh `uuid4` in-memory for the `uuid` field
5. Use the `Write` tool to drop the YAML file in the right directory

**The example file is the canonical truth.** If a schema reference
disagrees with the example, trust the example.

## The validation gate

After every batch of file writes, run:

```bash
keel validate --strict --format=json
```

Parse the JSON. Fix every error. Re-run. Repeat until `exit_code == 0`.
The command also rebuilds the graph cache as a side effect — no separate
rebuild step needed.

Full details: `references/VALIDATION.md`.

## Allocating IDs — the dual system

Every entity has **both** a canonical `uuid` and a human-readable `id`:

- **UUIDs**: generate yourself (`uuid4`) and put in frontmatter. No CLI
  call needed. Astronomically unlikely to collide.
- **Sequential issue keys** (`SEI-42`, etc.): call `keel next-key
  --type issue` **once per new issue**. Atomic under a file lock — safe
  even if other agents are running in parallel.
- **Node ids**: you pick the slug (`user-model`, `auth-token-endpoint`).
  No CLI call. Must be lowercase, letter-first, hyphenated.
- **Session ids**: you pick the slug (`wave1-agent-a`, `critical-fix`).

Full details: `references/ID_ALLOCATION.md`.

## The five mortal sins

These are the mistakes agents make most often. Each one fails validation
and costs you an iteration:

1. **Inventing fields** not in the schema. The validator rejects unknown
   frontmatter keys. Stick to what's in the example.
2. **Forgetting to run `validate`** before declaring done. Every time
   without exception.
3. **Forgetting to allocate via `next-key`**. Don't hand-pick issue
   numbers or read `next_issue_number` yourself — the counter drifts.
4. **Hand-writing UUIDs**. Use a real uuid4. The validator checks format.
5. **Producing dangling references** — `[[non-existent-node]]` or
   `blocked_by: [INVENTED-99]`. Only reference entities you've created
   or confirmed already exist in the project.

Full list with bad/good examples: `references/ANTI_PATTERNS.md`.

## Where to read next

- **Starting an initial scoping job?** → `references/WORKFLOWS_INITIAL_SCOPING.md`
- **Making a small update?** → `references/WORKFLOWS_INCREMENTAL_UPDATE.md`
- **Need the project config shape?** → `references/SCHEMA_PROJECT.md`
- **Need to understand the concept graph?** → `references/CONCEPT_GRAPH.md`
- **Errors from the validator you don't recognise?** → `references/VALIDATION.md`
- **Want to see a worked example first?** → `examples/issue-fully-formed.yaml`

Now: run `keel brief`, then read the workflow reference for the task
you're on.
