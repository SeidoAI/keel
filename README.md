<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)"  srcset="https://raw.githubusercontent.com/SeidoAI/tripwire/main/img/mark-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/SeidoAI/tripwire/main/img/mark-light.svg">
    <img alt="tripwire" src="https://raw.githubusercontent.com/SeidoAI/tripwire/main/img/mark-light.svg" width="360">
  </picture>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"></a>
  <a href="https://pypi.org/project/tripwire-pm/"><img src="https://img.shields.io/pypi/v/tripwire-pm" alt="PyPI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"></a>
</p>

> A git-native project-management framework for AI software teams. Tripwires catch drift; the concept graph stays canonical.

**[Quickstart](#quickstart)** · **[What you get](#what-you-get)** · **[Principles](#principles)** · **[Lifecycle](#v07-lifecycle-flow)** · **[Commands](#commands)** · **[Slash commands](#slash-commands)**

---

## Quickstart

```bash
pip install tripwire-pm
tw init my-project
cd my-project
claude
```

_(Distribution name is `tripwire-pm` because PyPI prohibits `tripwire`; the CLI — `tripwire` or `tw` — and `import tripwire` are unchanged.)_

Then in Claude Code:

```
/pm-scope Build a knowledge base with nodes and edges. Planning docs in ./plans/.
```

That's it. The agent reads your intent, scopes the project, writes the files,
validates its own work, and hands you a clean project to commit.

To see your project in the web dashboard:

```bash
tw ui
```

`tw init` auto-derives a key prefix from the project name (`my-project-cool` →
`MPC`), defaults to `main` as the base branch, and prompts for anything
non-obvious. Pass `--key-prefix`, `--base-branch`, or `--repos` to override.

### Minimal install

For CI pipelines or agents that only need the CLI (no web dashboard):

```bash
pip install "tripwire-pm[projects]"
```

## What you get

- **One repo, everything inside.** Issues, concept nodes, sessions, skills, templates, enums — all version-controlled in git. No external DB, no SaaS.
- **Dual ID system.** Canonical UUID + atomic human key (`MP-42`), allocated with `fcntl.flock`. Branch-merge safe.
- **Content-hashed concept graph.** `[[node-id]]` references point at file regions with SHA-256 hashes. Move code → one node updates → every downstream issue catches up. Drift is a validation error.
- **23-check validation gate.** Schema, references, bidirectional consistency, status transitions, freshness, per-issue artifact presence, Layer-3 session↔issue coherence, sequence drift. JSON output. Auto-fix subset. ~50 ms on a typical project. Rebuilds the graph cache as a side effect.
- **Session lifecycle commands.** `queue → spawn → monitor → review → complete` — each step is a CLI verb + a matching `/pm-session-*` slash command. Sessions produce per-issue `developer.md` and `verified.md` artifacts gated by status.
- **Agent insights capture.** Sessions propose concept-node additions/updates in `insights.yaml`; the PM reviews at complete time. Knowledge compounds across sessions rather than evaporating with the chat history.
- **Canonical YAML spawn config.** One place (`templates/spawn/defaults.yaml`) decides model, effort, budget, prompt, flags. Projects and sessions override by deep-merge.
- **Shipped PM skill.** 20 reference docs and 14 canonical example files ship into every `init`. The agent reads the example, not the schema doc.

## Principles

### 1. The graph is the synchronization layer that makes drift impossible

AI-driven work across issue trackers, docs, code comments, PR
descriptions, and ADRs produces redundant descriptions of the same
concept. Every copy drifts. Tripwire's concept graph is the single
source of truth for every domain concept the project models — issues,
PRs, code comments, READMEs, cross-repo workspace nodes reference
nodes by pointer (`[[node-id]]`). There is one place to update and
no alternative location for the same information to live.

### 2. Deviation is expected; tripwires catch what prevention can't

Agents drift during execution. Prevention cripples autonomy; tolerance
produces wrong PRs. Tripwire designs for the failure: validators emit
warnings into the agent's most recent context so they have a higher
probability of being addressed before the agent proceeds. Tripwires
are sensors, not locks — lightweight enough to preserve autonomy,
explicit enough to redirect cleanly.

### 3. Config over convention, with opinions

Tripwire ships opinionated defaults in YAML — how sessions should
spawn, what artifacts are required, what statuses mean, what the agent
spawn prompt should say. Projects override where they legitimately
differ. Tripwire is *not* configurable about validation-as-a-gate,
artifacts-as-evidence, single-agent-sessions, or the graph-as-canon
— softening those breaks the mechanism.

### 4. Work compounds; sessions are knowledge-producing events

A session's deliverable is the PR **plus** the updated concept nodes,
developer notes, and verified notes. A session that ships code without
updating what the project knows about itself has made the project
worse — the next agent inherits more confusion, not less. Status
advancement is gated on artifact production because artifacts are
where the knowledge lives.

### 5. Decomposition is a first-class product

Execution quality is bounded by framing quality. PM work — scoping,
plan writing, session layout, acceptance criteria, dependency DAGs —
is the highest-leverage work in the project, and the decomposition
itself is a deliverable that deserves quality, review, and iteration.
This is why tripwire has more PM-facing features than execution-facing
ones.

## How it works

**The concept graph is coherence.** Instead of prose like "the auth endpoint," issues reference `[[auth-token-endpoint]]` — a node file pointing at a specific file and line range with a stored content hash. When the code moves, one node updates; every issue that referenced it stays correct. Stale hashes surface as validator errors.

**Validation is the gate.** Every agent loop ends with `tw validate --strict --format=json`. The 23 checks cover schema, references, bidirectional consistency, status transitions, artifact presence, and session↔issue coherence. The same command rebuilds the graph cache incrementally. The loop is: write files → validate → fix → validate → commit.

**Sessions are knowledge-producing events.** A session doesn't end at the PR; it ends at `tw session complete`, which gates on the PR being merged, on per-issue artifacts (`developer.md`, `verified.md`) being present, and on the most recent review exit-code being ≤ 1. Any proposed concept-node updates (`insights.yaml`) get PM-reviewed before the session closes.

**The project ships its own instruction set.** `tw init` doesn't just create a data directory — it ships the PM skill (20 reference docs + 14 canonical examples), 23 slash commands, and the validation loop. The methodology is versioned in-tree with the project. Fork a project, fork the methodology. Evolve it in a PR, review it like code.

## v0.7 lifecycle flow

```
plan ──► queue ──► spawn ──► execute ──► monitor ──► review ──► complete
  │        │         │          │           │          │          │
  │        │         │          │           │          │          └─ gates on PR merged
  │        │         │          │           │          │             + artifacts present
  │        │         │          │           │          │             + review exit ≤ 1
  │        │         │          │           │          │             closes issues, cleans worktree,
  │        │         │          │           │          │             reviews insights
  │        │         │          │           │          └─ writes verified.md + review.json
  │        │         │          │           └─ one-shot / looped snapshot
  │        │         │          │              (turn, cost, latest tool, PR)
  │        │         │          └─ writes developer.md + task-checklist.md,
  │        │         │             opens PR
  │        │         └─ creates worktree + launches `claude -p` with resolved spawn config
  │        └─ readiness check: plan.md + verification-checklist.md present, blockers done
  └─ plan.md + verification-checklist.md written during scoping
```

Each step is a CLI verb (`tw session queue|spawn|monitor|review|complete`) and a matching `/pm-session-*` slash command. The verbs are mechanical; the slash commands add PM judgment.

## Commands

```text
tw init              Bootstrap a project with templates + skills
tw brief             Dump project context (agents use this on every loop)
tw validate          23-check gate (--strict, --fix, --format=json)
tw status            Dashboard: issues, nodes, sessions, critical path
tw agenda            Aggregated view of everything in flight
tw plan              Preview what init would produce (dry-run)
tw next-key          Atomic ID/key allocation (fcntl.flock)
tw uuid              Generate RFC 4122 UUID4 values (--count N)

tw session …         Session lifecycle: list/show/check/queue/spawn/
                     pause/abandon/cleanup/agenda/progress/monitor/
                     review/complete/insights/artifacts
tw issue …           Per-issue operations: artifact list/init/verify
tw workspace …       Multi-project workspace operations (v0.6b)
tw ci install        Render the project-side CI workflow

tw graph             Render dependency or concept graph (mermaid/dot/json)
tw refs              Inspect references to a node or issue
tw node              List, inspect, freshness-check concept nodes
tw templates         List and instantiate Jinja2 templates
tw enums             List active enum values
tw artifacts         List session artifact manifest
tw refresh           Rebuild the graph cache from filesystem
tw lint              Run per-stage lint rules (scoping/handoff/session)
tw ui                Start the web dashboard on localhost
tw view              Read-only HTML project viewer
tw completion <sh>   Print bash/zsh/fish tab completion install snippet
```

All commands output JSON by default (agent-first). Add `--format=text`
or `--format=rich` for human-readable output.

Run `tw --help` or `tw <cmd> --help` for details. The long name `tripwire` is an alias for `tw` — use either.

## Slash commands

After `tw init`, every project ships with `/pm-*` slash commands at
`.claude/commands/`. Type `/pm` in Claude Code to see them all at once.

### Scoping
| Command | Args | What it does |
|---|---|---|
| `/pm-scope` | `<intent>` | Scope a new project from your intent and planning docs |
| `/pm-rescope` | `<intent>` | Expand an existing project with new scope |
| `/pm-triage` | — | Process inbound suggestions, comments, and agent messages |
| `/pm-edit` | `<entity> <change>` | Surgical edit — status change, new node, comment, etc. |

### Sessions
| Command | Args | What it does |
|---|---|---|
| `/pm-session-create` | `<session-id>` | Create session YAML + plan skeleton |
| `/pm-session-queue` | `<session-id>` | Readiness check; transition planned → queued |
| `/pm-session-spawn` | `<session-id>` | Create worktree + launch `claude -p` |
| `/pm-session-check` | `<session-id>` | Readiness punch list (no transition) |
| `/pm-session-agenda` | — | Session dependency DAG with launch recommendations |
| `/pm-session-progress` | `[--focus ID]` | Task-checklist rollup across active sessions |
| `/pm-session-monitor` | `[ids...]` | Self-paced runtime observation |
| `/pm-session-review` | `<session-id>` | Review PR vs issue specs; writes `verified.md` |
| `/pm-session-complete` | `<session-id>` | Close-out gates; transition to done |

### Issues
| Command | Args | What it does |
|---|---|---|
| `/pm-issue-close` | `<issue-key>` | Mark issue done, write a closing comment |
| `/pm-issue-artifact` | `<key> <name>` | Create or update a per-issue artifact |

### Project / workspace
| Command | Args | What it does |
|---|---|---|
| `/pm-project-create` | `<name>` | Bootstrap a new project under a workspace |
| `/pm-project-sync` | — | Pull workspace-canonical nodes into the project |

### Interpretive
| Command | Args | What it does |
|---|---|---|
| `/pm-status` | — | PM-flavoured project summary with next-step recommendations |
| `/pm-agenda` | — | Interpreted summary of everything in flight |
| `/pm-graph` | — | Critical path, parallelizable work, cycles |
| `/pm-review` | `<PR>` | Review a PR against the project repo for quality + completeness |
| `/pm-validate` | — | Run the validator, interpret errors, propose fixes |
| `/pm-lint` | `<stage>` | Run a specific lint rule group (scoping/handoff/session) |

Each slash command loads the project-manager skill, reads current state via
`tw brief`, then executes the relevant workflow.

## Project layout

After `tw init`:

```text
my-project/
├── project.yaml                     # name, key_prefix, statuses, enum pointers, spawn_defaults
├── .tripwire/
│   ├── commands/                    # project-level slash-command overrides
│   └── spawn/                       # project-level spawn config overrides
├── enums/*.yaml                     # override shipped defaults (issue_status, session_status, …)
├── issues/<KEY>/
│   ├── issue.yaml                   # frontmatter + body
│   ├── developer.md                 # written at in_review
│   ├── verified.md                  # written at verified
│   └── comments/                    # one file per PM comment
├── nodes/*.yaml                     # concept graph (top-level)
├── sessions/<id>/
│   ├── session.yaml
│   ├── handoff.yaml                 # PM → execution-agent record
│   ├── plan.md                      # written during scoping
│   ├── task-checklist.md            # written during in_progress
│   ├── verification-checklist.md    # written during scoping
│   ├── recommended-testing-plan.md
│   ├── post-completion-comments.md
│   ├── review.json                  # written by `tw session review`
│   ├── insights.yaml                # agent-proposed node updates (optional)
│   └── artifacts/                   # overflow / custom artifacts
├── graph/index.yaml                 # derived cache (rebuildable)
├── templates/                       # project-local Jinja templates
└── .claude/
    ├── commands/pm-*.md             # 23 slash commands shipped
    └── skills/project-manager/      # 20 reference docs + 14 examples
```

---

<details>
<summary><b>Demo</b> — CLI samples</summary>

```text
$ tw validate --strict --format=json
{
  "version": 1,
  "exit_code": 0,
  "errors": [],
  "warnings": [],
  "fixed": [],
  "cache_rebuilt": true,
  "duration_ms": 47
}

$ tw status --format=rich
my-project (MP)
  Issues: 23  (backlog=8, todo=6, in_progress=4, in_review=3, verified=1, done=1)
  Concept nodes: 17 active, 2 stale
  Sessions: 4  (1 executing, 1 in_review, 2 completed)
  Critical path: MP-1 → MP-7 → MP-12 → MP-18  (length 4)

$ tw session monitor
session-auth-rework  executing  source=stream-json
  turn: 12
  cost: $0.84
  latest tool: Edit
  branch: feat/session-auth-rework (PR #42)

$ tw uuid --count 3
a1b2c3d4-e5f6-4789-abcd-ef0123456789
f9e8d7c6-b5a4-4321-8765-432109876543
12345678-90ab-4cde-8f01-234567890abc
```

</details>

<details>
<summary><b>Why drift matters</b> — the problem this solves</summary>

You can't run a real software project on a stack of LLM agents yet, and the reason is drift.

- **Your issue tracker drifts from your code.** You write "the auth endpoint in the backend" today; six weeks later that endpoint moves and the issue text doesn't. The next agent builds against stale information.
- **Your context is scattered.** The issue is in Linear, the decision is in Notion, the API contract is in a Google Doc, the schema is in a Terraform module. An agent piecing those together burns half its tokens on reconciliation.
- **You can't run multiple coding agents in parallel without a coordinator.** Each needs a branch, an issue key, an awareness of who owns what. Without atomic key allocation, they stomp on each other.
- **Drift is a tax on every future invocation.** Mechanical search-and-replace across docs, issues, code, and schemas is exactly what LLMs are bad at. Partial reconciliations leave the next agent with more drift to chase.

Tripwire fixes this by putting everything in one git repo with cross-referenced YAML, content-hashed concept nodes, and a 23-check validator that catches drift before the next agent reads it.

</details>

<details>
<summary><b>Under the hood</b> — dual IDs, graph cache, freshness</summary>

**Dual IDs.** Every entity has both a canonical `uuid4` (agent-generated, never changes) and a human key like `MP-42` (allocated atomically by `tw next-key` under `fcntl.flock`). Key collisions across branches are detected by the validator and resolved via the UUID, so references don't break.

**Concept graph with content hashing.** A concept node points at a region of a file in a repo:

```yaml
source:
  repo: myorg/backend
  path: src/api/routes/auth.py
  lines: [45, 82]
  branch: main
  content_hash: "sha256:e2c5a..."
```

`tw node check` fetches the current content (local clone preferred, `gh api` fallback) and compares SHA-256 hashes. Three outcomes: `FRESH`, `STALE`, `SOURCE_MISSING`. Stale nodes become validator errors.

**Graph cache.** `graph/index.yaml` is an incremental cache of all edges, rebuilt under `fcntl.flock`. `validate` calls `ensure_fresh` which picks between incremental update and full rebuild based on current state.

**Auto-fix subset.** `tw validate --fix` repairs: missing timestamps (from file mtime), drifted `next_issue_number`, missing UUIDs, bidirectional `related` mismatches, label/list normalisation, basic ID collision renames. Everything else is on the agent.

**Canonical spawn config.** `tw session spawn` builds the `claude -p` argv from a deep-merged YAML (`session.spawn_config` > `project.spawn_defaults` > `.tripwire/spawn/defaults.yaml` > shipped default). Every flag — `--name`, `--session-id`, `--effort`, `--model`, `--fallback-model`, `--permission-mode`, `--disallowedTools`, `--max-turns`, `--max-budget-usd`, `--output-format`, `--append-system-prompt` — is parameterised; override what matters, inherit the rest.

**The PM skill.** `.claude/skills/project-manager/` ships into every `init` with 20 reference docs (workflows, schemas, validation codes, anti-patterns) and 14 canonical example files. When the agent is confused it reads the example. When the example is wrong the validator catches it.

</details>

<details>
<summary><b>Worked example</b> — scoping from raw planning docs</summary>

1. `tw init my-project` creates the project with templates, skill files, 23 slash commands, and enums. Auto-derives the key prefix from the name (`my-project` → `MP`).
2. You open Claude Code in `my-project/` and type: `/pm-scope Build a knowledge base. Planning docs in ./plans/.`
3. The PM skill auto-loads. It calls `tw brief` to read project state, then reads `plans/*.md`.
4. The agent calls `tw next-key --type issue` 20 times, writes 20 issue YAML files into `issues/`, writes 15 concept nodes into `nodes/`, writes 3 session folders into `sessions/`.
5. It runs `tw validate --strict --format=json`, parses the JSON, fixes any `ref/dangling`, `body/missing_heading`, or `status/unreachable` errors, re-runs.
6. Clean. The agent commits the result. You `tw status` and see a connected dependency graph with a critical path.

Everything is in git. Every reference resolves. Every concept node's content hash is current. The next agent that picks up a ticket has the full picture from one clone.

</details>

<details>
<summary><b>What we learned building this</b></summary>

Running a real PM agent against an 8,000-line planning corpus surfaced seven recurring failure modes — agents don't self-check unless forced; every workflow step must be load-bearing; agents anchor, rationalise, and reason as if they were human; output degrades over session length; structure and semantics are different problems; when in doubt create the node; the project must ship its own instruction set.

See [`docs/learnings.md`](docs/learnings.md) for the full write-up.

</details>

---

## License

MIT. See `LICENSE`.
