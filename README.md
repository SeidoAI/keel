# Agent Projects

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> A git-native project tracker where the PM, coders, and verifier are AI agents.

Issues, architecture decisions, contracts, sessions — all YAML files in one
git repo, all cross-referenced, all validated by one 50 ms gate. Designed so
Claude Code (or any agent with file-write tools) can scope, track, and ship
real software projects without drifting from the code.

**[Quickstart](#quickstart)** · **[What it does](#what-it-does)** · **[How it works](#how-it-works)** · **[Commands](#commands)** · **[Docs](#docs)**

---

## Quickstart

```bash
pip install agent-project

agent-project init my-project --key-prefix MP --base-branch main
cd my-project
agent-project scaffold-for-creation
```

Open Claude Code in `my-project/`, load `.claude/skills/project-manager/SKILL.md`,
and ask it to scope your planning docs. After each batch of file writes:

```bash
agent-project validate --strict --format=json
```

Exit 0 → commit. Exit non-zero → the agent has the JSON report and fixes itself.

## What it does

- **One repo, everything inside.** Issues, concept nodes, sessions, skills, templates, enums — all version-controlled in git. No external DB, no SaaS.
- **Dual ID system.** Canonical UUID + atomic human key (`MP-42`), allocated with `fcntl.flock`. Branch-merge safe.
- **Content-hashed concept graph.** `[[node-id]]` references point at file regions with SHA-256 hashes. Move code → one node updates → every downstream issue catches up. Drift is a validation error.
- **14-check validation gate.** Schema, references, bidirectional consistency, status transitions, freshness, sequence drift. JSON output. Auto-fix subset. ~50 ms on a typical project. Rebuilds the graph cache as a side effect.
- **One-shot context dump.** `scaffold-for-creation` gives an agent config, enums, templates, skill examples, next IDs, and the validation loop in a single tool-call result.
- **Customisable session artifacts.** Plans, task checklists, verification checklists, testing plans, post-completion comments — per-project manifest, enforced by the validator.
- **Progressive-disclosure PM skill.** 33 reference files and canonical examples ship into every `init`. The agent reads the example, not the schema doc.

## Demo

```text
$ agent-project validate --strict --format=json
{
  "exit_code": 0,
  "errors": [],
  "warnings": [],
  "fixed": [],
  "cache_rebuilt": true,
  "duration_ms": 47
}

$ agent-project status
my-project (MP)
  Issues: 23  (backlog=12, todo=8, in_progress=3)
  Concept nodes: 17 active, 2 stale
  Sessions: 4  (2 completed, 1 in_progress, 1 waiting_for_review)
  Critical path: MP-1 → MP-7 → MP-12 → MP-18  (length 4)
```

## How it works

Four principles. Each one is a deliberate choice.

**1. The project repo is the single source of truth.** Nothing lives in Linear, Notion, or a Google Doc. Clone the repo and you have the whole project.

**2. Agents are the primary users.** The CLI is intentionally minimal — read, validate, atomic ID allocation. Agents create issues and nodes by writing files directly with their `Write` tool, then run the validator.

**3. The concept graph is coherence.** Instead of prose like "the auth endpoint," issues reference `[[auth-token-endpoint]]` — a node file pointing at a specific file and line range with a stored content hash. When the code moves, one file updates. Stale hashes surface as validator errors.

**4. Validation is the gate.** Every agent loop ends with `agent-project validate --strict --format=json`. The same command rebuilds the graph cache incrementally. The loop is: write files → validate → fix → validate → commit.

## Commands

```text
agent-project init                     Bootstrap a project with templates + skills
agent-project scaffold-for-creation    Dump full project context for an agent
agent-project next-key                 Atomic ID/key allocation (fcntl.flock)
agent-project validate                 14-check gate  (--strict, --fix, --format=json)
agent-project status                   Dashboard: issues, nodes, sessions, critical path
agent-project graph                    Render dependency or concept graph (mermaid/dot/json)
agent-project refs                     Inspect references to a node or issue
agent-project node                     List, inspect, freshness-check concept nodes
agent-project templates                List and instantiate Jinja2 templates
agent-project enums                    List active enum values
agent-project artifacts                List session artifact manifest
agent-project completion <shell>       Print bash/zsh/fish tab completion install snippet
```

Run `agent-project --help` or `agent-project <cmd> --help` for details.

## Project layout

After `agent-project init`:

```text
my-project/
├── project.yaml              # one config file
├── issues/MP-*.yaml          # issue files (one per entity)
├── graph/
│   ├── nodes/*.yaml          # concept nodes
│   └── index.yaml            # derived cache (rebuildable)
├── sessions/sess-*/          # one folder per agent session
│   ├── session.yaml
│   ├── plan.md
│   ├── task-checklist.md
│   ├── verification-checklist.md
│   ├── recommended-testing-plan.md
│   └── post-completion-comments.md
├── enums/*.yaml              # customisable per project
├── orchestration/default.yaml
├── templates/                # Jinja2 templates the agent renders
└── .claude/skills/           # progressive-disclosure agent guidance
    ├── project-manager/
    ├── backend-development/
    ├── frontend-development/
    └── verification/
```

---

<details>
<summary><b>Why drift matters</b> — the problem this solves</summary>

You can't run a real software project on a stack of LLM agents yet, and the reason is drift.

- **Your issue tracker drifts from your code.** You write "the auth endpoint in the backend" today; six weeks later that endpoint moves and the issue text doesn't. The next agent builds against stale information.
- **Your context is scattered.** The issue is in Linear, the decision is in Notion, the API contract is in a Google Doc, the schema is in a Terraform module. An agent piecing those together burns half its tokens on reconciliation.
- **You can't run multiple coding agents in parallel without a coordinator.** Each needs a branch, an issue key, an awareness of who owns what. Without atomic key allocation, they stomp on each other.
- **Drift is a tax on every future invocation.** Mechanical search-and-replace across docs, issues, code, and schemas is exactly what LLMs are bad at. Partial reconciliations leave the next agent with more drift to chase.

`agent-project` fixes this by putting everything in one git repo with cross-referenced YAML, content-hashed concept nodes, and a 14-check validator that catches drift before the next agent reads it.

</details>

<details>
<summary><b>Under the hood</b> — dual IDs, graph cache, freshness, orchestration</summary>

**Dual IDs.** Every entity has both a canonical `uuid4` (agent-generated, never changes) and a human key like `MP-42` (allocated atomically by `next-key` under `fcntl.flock`). Key collisions across branches are detected by the validator and resolved via the UUID, so references don't break.

**Concept graph with content hashing.** A concept node points at a region of a file in a repo:

```yaml
source:
  repo: myorg/backend
  path: src/api/routes/auth.py
  lines: [45, 82]
  branch: main
  content_hash: "sha256:e2c5a..."
```

`agent-project node check` fetches the current content (local clone preferred, `gh api` fallback) and compares SHA-256 hashes. Three outcomes: `FRESH`, `STALE`, `SOURCE_MISSING`. Stale nodes become validator errors.

**Graph cache.** `graph/index.yaml` is an incremental cache of all edges, rebuilt under `fcntl.flock`. `validate` calls `ensure_fresh` which picks between incremental update and full rebuild based on the current state.

**Auto-fix subset.** `validate --fix` repairs: missing timestamps (from file mtime), drifted `next_issue_number`, missing UUIDs, bidirectional `related` mismatches, label/list normalisation, basic ID collision renames. Everything else is on the agent.

**Orchestration patterns.** Declarative YAML rules for when humans approve, when the PM auto-acts, when sessions merge on pass:

```yaml
events:
  on_session_complete:
    - condition: "verification.passed"
      action: "merge_branch"
    - condition: "verification.failed"
      action: "request_human_review"
```

Per-project defaults in `orchestration/default.yaml`; per-session overrides in the session folder. The runtime that consumes them (see `docs/agent-containers.md`) is configured *by* the project repo, not the other way round.

**The PM skill.** `.claude/skills/project-manager/` ships into every `init` with 17 reference docs (workflows, schemas, validation codes, anti-patterns) and 13 canonical example files. When the agent is confused it reads the example. When the example is wrong the validator catches it.

</details>

<details>
<summary><b>Worked example</b> — scoping from raw planning docs</summary>

1. `agent-project init my-project --key-prefix MP --base-branch main` creates the project with 73 templates, 43 skill files, 11 enums.
2. `agent-project scaffold-for-creation` prints the project config, active enums, artifact manifest, templates, skill examples, and the next issue/session keys — all in one block.
3. You open Claude Code in `my-project/` and tell it: *"You are the project manager. Load `.claude/skills/project-manager/SKILL.md` and read `raw_planning/*.md`. Scope the project."*
4. The agent calls `agent-project next-key --type issue` 20 times, writes 20 issue YAML files into `issues/`, writes 15 concept nodes into `graph/nodes/`, writes 3 session folders into `sessions/`.
5. It runs `agent-project validate --strict --format=json`, parses the JSON, fixes any `ref/dangling`, `body/missing_heading`, or `status/unreachable` errors, re-runs.
6. Exit 0. The agent commits the result. You `agent-project status` and see a connected dependency graph with a critical path.

Everything is in git. Every reference resolves. Every concept node's content hash is current. The next agent that picks up a ticket has the full picture from one clone.

</details>

---

## Status

**v0.** 362 tests pass. The validation gate is stable. The PM skill ships into every initialised project. APIs may change before v1.

**Not in v0:** web UI, managed cloud version, the agent execution runtime itself. Those are tracked in `docs/agent-containers.md` and `docs/agent-projects-ui.md`.

## Docs

- Design: `docs/agent-projects-plan.md`
- Agent execution runtime: `docs/agent-containers.md`
- Web dashboard: `docs/agent-projects-ui.md`
- Platform plan: `docs/overarching-plan.md`

## License

MIT. See `LICENSE`.
