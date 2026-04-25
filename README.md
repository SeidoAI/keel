<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)"  srcset="https://raw.githubusercontent.com/SeidoAI/tripwire/main/img/mark-accent-cream.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/SeidoAI/tripwire/main/img/mark-accent.svg">
    <img alt="tripwire" src="https://raw.githubusercontent.com/SeidoAI/tripwire/main/img/mark-accent.svg" width="360">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/SeidoAI/tripwire/actions/workflows/ci.yml"><img src="https://github.com/SeidoAI/tripwire/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"></a>
  <a href="https://pypi.org/project/tripwire-pm/"><img src="https://img.shields.io/pypi/v/tripwire-pm" alt="PyPI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"></a>
</p>

> A git-native project-management framework for AI software teams working on large projects. Tripwires catch workflow drift during a session; the concept graph prevents definition drift across the project.

**[Quickstart](#quickstart)** · **[What you get](#what-you-get)** · **[Principles](#principles)** · **[Lifecycle](#v07-lifecycle-flow)** · **[Commands](#commands)** · **[Slash commands](#slash-commands)**

---

## Quickstart

```bash
pip install tripwire-pm
tw init my-project
cd my-project
claude
```

Then in Claude Code:

```
/pm-scope Build a knowledge base with nodes and edges. Planning docs in ./plans/.
```

`tw init` creates issue keys from your project name (`my-project-cool` → `MPC`).

Web dashboard: `tw ui`.

### Minimal install

```bash
pip install "tripwire-pm[projects]"
```

## What you get

- **Agents drift, skip stages, degrade over time, and sometimes lie about their work - worse on bigger projects.** Tripwires fire at workflow checkpoints and inject just-in-time instructions into the agent's *most recent* turn; **LLM recency bias** makes them pay attention. Think sensors, not locks.
- **Descriptions go stale the moment code moves.** The concept graph anchors every reference: `[[node-id]]` points at a file region with a SHA-256 content hash. Move the code, the graph catches up. Stale refs are *validator errors*, not silent lies.
- **Every session starts from zero.** Sessions propose graph updates in `insights.yaml`; the PM reviews them at close-out. Knowledge **compounds** instead of evaporating with the chat history.
- **You can't tell if an agent's work is actually done.** 23-check validator runs in ~50 ms. Artifacts (`developer.md`, `verified.md`) gate status transitions — no handwaving through `in_review`.
- **You're babysitting `claude -p` in a terminal.** `queue → spawn → monitor → review → complete` turns each stage into a CLI verb *and* a `/pm-session-*` slash command. Each stage gates the next.
- **Your methodology is trapped in someone else's cloud.** Issues, nodes, sessions, skills, templates, validation loop — all git. `tw init` ships the PM skill *into the repo*. Fork the project, fork the methodology.
- **Parallel agents collide on keys.** Dual IDs — UUID + atomic human key (`MP-42`). `tw next-key` is branch-merge safe.
- **Agents burn context reading schemas.** PM skill ships **20 reference docs + 14 canonical examples**. The agent reads the example, not the schema.

## Principles

### 1. The graph is where domain knowledge lives

When the same concept gets described in five places — issue text, PR descriptions, code comments, docs — each copy ages independently. The graph keeps one canonical definition per concept; everything else references it by pointer (`[[node-id]]`). If there's only one place the information lives, there's nothing to go out of sync.

### 2. Agents drift; tripwires catch it

Agents skip stages, fudge artifacts, degrade over long sessions, and occasionally claim work they haven't done. Blocking every step cripples autonomy; ignoring the problem ships bad PRs. Tripwires sit between those: validators drop warnings into the agent's *most recent* context, so **recency bias** makes them likely to land before the next action. Sensors, not locks.

### 3. Opinionated defaults, fully configurable

Tripwire ships opinions on every question the agent shouldn't have to answer: what statuses mean, which transitions are legal, what artifacts a phase requires, how sessions spawn, what prompts the agent gets. Projects override any of them via YAML. Nothing is hardcoded, nothing is neutral. Every default is an opinion you can reshape when your project needs something different.

### 4. Sessions produce knowledge, not just code

A session's deliverable is the PR *plus* updated concept nodes, developer notes, and verified notes. A session that ships code without updating what the project knows has made the project worse - the next agent inherits more confusion, not less. That's why status advancement gates on artifact production: the artifacts are where the knowledge lives.

### 5. Framing is where execution quality comes from

Scoping, plan writing, session layout, acceptance criteria, dependency DAGs — how well you frame the work bounds how well it can be executed. The decomposition itself deserves review and iteration. Tripwire has more PM-facing features than execution-facing ones on purpose.

## How it works

**The graph is coherence.** Issues reference `[[auth-token-endpoint]]`, not prose. Move the code, update the node, every reference catches up. Drift is a validator error.

**Validation is the gate.** Every loop ends with `tw validate --strict`. Write → validate → fix → validate → commit.

**Sessions are knowledge-producing events.** A session ends at `tw session complete`, which gates on PR merged, artifacts present, and review exit-code ≤ 1. Proposed graph updates get PM-reviewed before close-out.

**The project ships its own instruction set.** `tw init` ships the PM skill, slash commands, and validation loop into the repo. Fork the project, fork the methodology.

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

Each step is a CLI verb and a matching `/pm-session-*` slash command. The verbs are mechanical; the slash commands add PM judgment.

## Commands

```text
tw init              Bootstrap a project
tw brief             Dump project context
tw validate          23-check gate
tw status            Dashboard
tw agenda            In-flight view
tw plan              Dry-run init
tw next-key          Atomic key allocation
tw uuid              Generate UUID4

tw session …         Session lifecycle
tw issue …           Per-issue artifacts
tw workspace …       Multi-project workspace
tw ci install        Project CI workflow

tw graph             Render dependency or concept graph
tw refs              Inspect references
tw node              Freshness-check nodes
tw templates         List and instantiate templates
tw enums             List active enum values
tw artifacts         List artifact manifest
tw refresh           Rebuild the graph cache
tw lint              Per-stage lint rules
tw ui                Web dashboard
tw view              HTML project viewer
tw completion <sh>   Shell tab-completion
```

Default output is JSON; add `--format=text` or `--format=rich` for humans. Run `tw --help` for details.

## Slash commands

After `tw init`, `/pm-*` commands ship at `.claude/commands/`. Type `/pm` in Claude Code to list them.

### Scoping
| Command | Args | What it does |
|---|---|---|
| `/pm-scope` | `<intent>` | Scope a new project |
| `/pm-rescope` | `<intent>` | Expand existing scope |
| `/pm-triage` | — | Process inbound suggestions |
| `/pm-edit` | `<entity> <change>` | Surgical edit |

### Sessions
| Command | Args | What it does |
|---|---|---|
| `/pm-session-create` | `<session-id>` | Create session YAML |
| `/pm-session-queue` | `<session-id>` | Readiness check; queue |
| `/pm-session-spawn` | `<session-id>` | Worktree + launch `claude -p` |
| `/pm-session-check` | `<session-id>` | Readiness punch list |
| `/pm-session-agenda` | — | Session dependency DAG |
| `/pm-session-progress` | `[--focus ID]` | Task-checklist rollup |
| `/pm-session-monitor` | `[ids...]` | Runtime observation |
| `/pm-session-review` | `<session-id>` | Review PR; write `verified.md` |
| `/pm-session-complete` | `<session-id>` | Close-out gates |

### Issues
| Command | Args | What it does |
|---|---|---|
| `/pm-issue-close` | `<issue-key>` | Mark done; write close comment |
| `/pm-issue-artifact` | `<key> <name>` | Create or update issue artifact |

### Project / workspace
| Command | Args | What it does |
|---|---|---|
| `/pm-project-create` | `<name>` | Bootstrap project under workspace |
| `/pm-project-sync` | — | Pull canonical nodes from workspace |

### Interpretive
| Command | Args | What it does |
|---|---|---|
| `/pm-status` | — | Summary + next-step recommendations |
| `/pm-agenda` | — | In-flight summary |
| `/pm-graph` | — | Critical path, parallel work, cycles |
| `/pm-review` | `<PR>` | Review a PR |
| `/pm-validate` | — | Run validator; interpret and fix |
| `/pm-lint` | `<stage>` | Per-stage lint rules |

## Project layout

After `tw init`:

```text
my-project/
├── project.yaml                     # project config
├── .tripwire/
│   ├── commands/                    # slash-command overrides
│   └── spawn/                       # spawn-config overrides
├── enums/*.yaml                     # project-level enum overrides
├── issues/<KEY>/
│   ├── issue.yaml
│   ├── developer.md                 # written at in_review
│   ├── verified.md                  # written at verified
│   └── comments/
├── nodes/*.yaml                     # concept graph
├── sessions/<id>/
│   ├── session.yaml
│   ├── handoff.yaml                 # PM → agent record
│   ├── plan.md
│   ├── task-checklist.md
│   ├── verification-checklist.md
│   ├── recommended-testing-plan.md
│   ├── post-completion-comments.md
│   ├── review.json                  # `tw session review` output
│   ├── insights.yaml                # proposed node updates
│   └── artifacts/
├── graph/index.yaml                 # derived cache
├── templates/
└── .claude/
    ├── commands/pm-*.md             # 23 slash commands
    └── skills/project-manager/      # 20 refs + 14 examples
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
<summary><b>Why drift matters</b></summary>

Agents can't build against a tracker that lies to them.

- **Issue text drifts from code.** The endpoint moves; the issue doesn't. Next agent builds against stale info.
- **Context is scattered.** Linear, Notion, Google Docs, Terraform. Agents burn tokens reconciling.
- **Parallel agents stomp.** Without atomic key allocation, they collide on branches and IDs.
- **Reconciliation is a tax.** Mechanical search-and-replace across docs is exactly what LLMs are bad at.

Tripwire puts everything in one repo, content-hashes the graph, and validates before the next agent reads it.

</details>

<details>
<summary><b>Under the hood</b> — dual IDs, graph cache, freshness</summary>

**Dual IDs.** Every entity has a `uuid4` and a human key like `MP-42`, allocated under `fcntl.flock`. Branch-merge collisions resolve via UUID.

**Concept graph with content hashing.** A node pins to a file region:

```yaml
source:
  repo: myorg/backend
  path: src/api/routes/auth.py
  lines: [45, 82]
  content_hash: "sha256:e2c5a..."
```

`tw node check` rehashes and compares. Outcomes: `FRESH` / `STALE` / `SOURCE_MISSING`.

**Graph cache.** `graph/index.yaml` is an incremental edge cache, rebuilt under `fcntl.flock`. `validate` calls `ensure_fresh`.

**Auto-fix subset.** `tw validate --fix` repairs timestamps, drifted counters, missing UUIDs, and bidirectional mismatches. Everything else is on the agent.

**Canonical spawn config.** `claude -p` args come from deep-merged YAML (session > project > default). Override the keys you care about; inherit the rest.

**The PM skill.** 20 reference docs and 14 canonical examples. The agent reads the example; the validator catches bad examples.

</details>

<details>
<summary><b>Worked example</b> — scoping from planning docs</summary>

1. `tw init my-project` — derives `MP` from the name.
2. `/pm-scope Build a knowledge base. Planning docs in ./plans/.`
3. The PM skill calls `tw brief`, then reads `plans/*.md`.
4. The agent writes 20 issues, 15 nodes, 3 sessions.
5. `tw validate --strict` — fix errors, re-run, clean.
6. Commit. `tw status` shows a connected graph with a critical path.

Everything resolves. One clone carries the whole project.

</details>

<details>
<summary><b>What we learned building this</b></summary>

Running a real PM agent against an 8,000-line planning corpus surfaced seven recurring failure modes.

See [`learnings.md`](https://github.com/SeidoAI/tripwire-workspace/blob/main/docs/learnings.md) in the tripwire-workspace repo.

</details>

---

## License

MIT. See `LICENSE`.
