# Plan v2: `agent-project` — Git-Native Agent Project Management Framework

## Context

We're replacing Linear + Notion with a single git-native project management system designed for AI agent collaboration. The current system (`linear-project-manager` skill in `ide-config`) is comprehensive but suffers from:
- **Slow feedback loops**: human-in-the-loop when not needed
- **Alignment drift**: three canonical sources (Notion, Linear, code) that fall out of sync
- **Agent navigation problems**: disparate docs are hard for agents to find and use
- **No automated status transitions**: status changes require manual intervention

**Phase 1 (this plan)** focuses on the **data layer** — an installable Python package that manages issues, concept graph, dependencies, status, and agent sessions as files in a git repo. Automation (GitHub Actions, agent triggering) and UI come later.

**Target directory**: `/Users/maia/Code/seido/projects/agent-projects/`

---

## Decisions

- **Package name**: `agent-project` (generic, not Seido-branded)
- **CLI command**: `agent-project`
- **File format**: YAML frontmatter + Markdown body (`.yaml` extension, `---` separator)
- **Status flow**: Full 9-status flow as default, configurable per project
- **Build system**: `hatchling` (matches existing ecosystem)
- **CLI framework**: `click` (mature, explicit, no magic)
- **Linting**: `ruff` (line-length 88, matching existing conventions)
- **Concept graph**: File-based nodes in `graph/nodes/`, content-hash staleness detection
- **Repo resolution**: Local clone preferred, GitHub API fallback

---

## The Coherence Problem and the Concept Graph

### Why this matters

The single biggest problem in agent-driven development is **coherence drift**. When an issue says "implement the `/auth/token` endpoint per the API contract," three things can drift independently:

1. The issue description (static once written)
2. The actual code (changes via PRs)
3. The contract document (changes separately)

Nobody notices until an agent picks up a downstream ticket and builds against stale information. This creates cascading failures: wrong API contracts, mismatched schemas, broken integrations — all because the references in tickets are just prose, not live links.

Beyond the integrity problem, drift directly damages agents in two ways:

**Agent confusion**: When the issue, the contract, and the code disagree, the agent has to guess which is authoritative. It often picks wrong, building against stale information. The damage compounds as downstream tickets pick up the wrong version. By the time the contradiction surfaces, it's wedged into multiple PRs.

**Drift fixes burn tokens**: Reconciling drift means finding every location where an old value lives — issues, comments, doc files, code, tests, terraform, schemas — and updating each one. This is exactly the kind of mechanical, repetitive search-and-replace work that LLMs are bad at: they miss instances, they update inconsistently, and they have to re-read enormous amounts of context to find each occurrence. The compute cost is high, the result is imperfect, and the next agent to read the codebase has to deal with whatever stragglers were missed. **Drift is a tax on every future agent invocation.**

### The solution: concept nodes as stable references

A **concept node** is a named, versioned pointer to a concrete artifact in the codebase. Instead of prose like "the auth endpoint in the backend," issues reference `[[auth-token-endpoint]]` — a stable identifier that resolves to a specific file, line range, and content hash.

This gives us three things:
1. **Indirection**: When code moves, update one node file instead of N issues
2. **Staleness detection**: Content hashing tells us when referenced code has changed
3. **Cross-repo linking**: A terraform output in one repo can be referenced by a backend issue in another

### Explicit nodes vs implicit references — when to use each

Not everything needs a node. The rule is simple:

**Create a node when a concept is referenced by multiple issues or across repos.** Think of nodes as named bookmarks into the codebase. A one-off file mention in a single issue stays as inline prose.

The practical workflow: when a coding agent implements something that other issues will need to reference (a new endpoint, a new model, a terraform output), the PM agent creates a node for it during the update workflow. This is already part of the existing linear-project-manager update workflow — we're just giving it a concrete mechanism.

### Why content hashing beats commit-based checking

We store a SHA-256 hash of the content at the referenced location (specific file + line range). On validation:

1. Fetch current content of the file at those lines (locally or via GitHub API)
2. Hash it
3. Compare to stored `content_hash`
4. **Different hash = content changed = reference potentially stale**

Why this is better than tracking commits:
- **Precise**: A commit might change line 90 but not lines 45-82. No false positive.
- **Works without git history**: Just needs the file content. Works via GitHub API for remote repos.
- **Works across repos**: No need to track which commits touched what — just compare hashes.
- **Detects meaningful changes**: A commit that only changed whitespace elsewhere doesn't trigger a false alarm.

### The PM agent as graph maintainer

The concept graph is not maintained by humans. It's maintained by agents as part of their existing workflows:

**Coding agent** (during implementation):
- Creates nodes for new artifacts it built (endpoints, models, configs)
- References existing nodes in its PR description and completion comment via `[[node-id]]`
- Updates existing nodes if it modified referenced code (rehash)

**PM agent** (during update workflow — already defined in the current skill):
- Runs `agent-project node check` to detect stale nodes after an issue completes
- Updates node `source` fields when code has moved
- Rehashes content after updates
- Identifies downstream issues that reference changed nodes
- Proposes issue updates as PRs when staleness is detected

**PM agent** (during creation/triage):
- When writing new issues, references existing nodes instead of prose descriptions
- Creates placeholder nodes (status: `planned`) for things that don't exist yet but will

This means graph maintenance is **not an additional task** — it's woven into the workflows agents already perform.

---

## Package Structure

```
agent-projects/                          # /Users/maia/Code/seido/projects/agent-projects/
├── pyproject.toml
├── Makefile
├── src/
│   └── agent_project/
│       ├── __init__.py
│       ├── models/                      # Pydantic v2 data models
│       │   ├── __init__.py
│       │   ├── enums.py                 # IssueStatus, Priority, Executor, Verifier, NodeType, etc.
│       │   ├── issue.py                 # Issue model
│       │   ├── project.py               # ProjectConfig model
│       │   ├── comment.py               # Comment model
│       │   ├── node.py                  # ConceptNode model (concept graph)
│       │   ├── session.py               # AgentSession, Wave, AgentDivisionPlan
│       │   └── graph.py                 # DependencyGraphResult, FullGraphResult (computed)
│       │
│       ├── core/                        # Business logic (stateless)
│       │   ├── __init__.py
│       │   ├── store.py                 # Read/write issues, project config, comments from disk
│       │   ├── node_store.py            # Read/write concept nodes, index generation
│       │   ├── parser.py                # YAML frontmatter + Markdown body parsing
│       │   ├── reference_parser.py      # Extract [[node-id]] references from Markdown bodies
│       │   ├── freshness.py             # Content hashing + staleness detection (local + GitHub API)
│       │   ├── validator.py             # Issue quality validation (from validate_agent_issue.py)
│       │   ├── dependency_graph.py      # Issue dependency graph (from dependency_graph.py)
│       │   ├── concept_graph.py         # Full graph: issues + nodes + edges (unified view)
│       │   ├── status.py                # Status transitions, dashboard aggregation
│       │   ├── id_generator.py          # Auto-increment <PREFIX>-<N> keys
│       │   ├── enum_loader.py           # NEW: dynamic enum loading from <project>/enums/
│       │   ├── graph_cache.py           # NEW: incremental graph index cache (v2 schema)
│       │   └── pm_review.py             # NEW: PM agent PR review checks (CheckResult API)
│       │   #
│       │   # NOTE: the orchestration RUNTIME lives in the agent-containers package
│       │   # (`agent_containers/core/orchestration.py`), NOT here. The agent-project
│       │   # package owns the data models and CLI for managing patterns; the runtime
│       │   # that reads patterns and dispatches actions ships with agent-containers.
│       │
│       ├── cli/                         # Click CLI
│       │   ├── __init__.py
│       │   ├── main.py                  # Root group + global options
│       │   ├── init.py                  # `agent-project init` (also `init --update`)
│       │   ├── issue.py                 # `agent-project issue {create,list,show,update,validate}`
│       │   ├── node.py                  # `agent-project node {create,list,show,check,update}`
│       │   ├── refs.py                  # `agent-project refs {list,reverse,check}`
│       │   ├── status.py                # `agent-project status`
│       │   ├── graph.py                 # `agent-project graph` (dependency + concept)
│       │   ├── session.py               # `agent-project session {create,list}`
│       │   ├── pm.py                    # NEW: `agent-project pm review-pr <pr-number>`
│       │   ├── templates.py             # NEW: `agent-project templates {list,show}`
│       │   ├── enums.py                 # NEW: `agent-project enums {list,show}`
│       │   ├── artifacts.py             # NEW: `agent-project artifacts {list,show}`
│       │   └── orchestrate.py           # NEW: `agent-project orchestrate evaluate <event-file>`
│       │
│       ├── templates/                   # Defaults shipped with the package, copied on init
│       │   ├── __init__.py              # Template loader
│       │   ├── project/
│       │   │   ├── project.yaml.j2
│       │   │   ├── CLAUDE.md.j2
│       │   │   └── gitignore.j2
│       │   ├── enums/                   # NEW: customisable enums
│       │   │   ├── issue_status.yaml
│       │   │   ├── priority.yaml
│       │   │   ├── executor.yaml
│       │   │   ├── verifier.yaml
│       │   │   ├── node_type.yaml
│       │   │   ├── node_status.yaml
│       │   │   ├── session_status.yaml
│       │   │   ├── re_engagement_trigger.yaml
│       │   │   ├── message_type.yaml
│       │   │   └── agent_state.yaml
│       │   ├── issue_templates/
│       │   │   ├── default.yaml.j2
│       │   │   ├── bug.yaml.j2
│       │   │   ├── decision.yaml.j2
│       │   │   └── investigation.yaml.j2
│       │   ├── comment_templates/       # NEW: comment scaffolds
│       │   │   ├── status_change.yaml.j2
│       │   │   ├── question.yaml.j2
│       │   │   └── completion.yaml.j2
│       │   ├── artifacts/               # NEW: session output templates
│       │   │   ├── manifest.yaml        # declares the active artifact set
│       │   │   ├── plan.md.j2
│       │   │   ├── task-checklist.md.j2
│       │   │   ├── verification-checklist.md.j2
│       │   │   ├── recommended-testing-plan.md.j2
│       │   │   └── post-completion-comments.md.j2
│       │   ├── agent_templates/         # default agent definitions
│       │   │   ├── backend-coder.yaml
│       │   │   ├── frontend-coder.yaml
│       │   │   ├── verifier.yaml
│       │   │   └── pm.yaml
│       │   ├── session_templates/       # NEW
│       │   │   └── default.yaml.j2
│       │   ├── orchestration/           # NEW: default patterns + hook scaffold
│       │   │   ├── default.yaml
│       │   │   ├── strict.yaml
│       │   │   ├── fast.yaml
│       │   │   └── hooks/
│       │   │       └── __init__.py
│       │   ├── skills/                  # ALL skills, copied into <project>/.claude/skills/
│       │   │   ├── agent-messaging/     # default messaging skill (every agent gets this)
│       │   │   │   ├── SKILL.md
│       │   │   │   └── references/
│       │   │   │       ├── MESSAGE_TYPES.md
│       │   │   │       ├── EXAMPLES.md
│       │   │   │       └── ANTI_PATTERNS.md
│       │   │   ├── project-manager/     # PM agent skill
│       │   │   │   ├── SKILL.md
│       │   │   │   └── references/
│       │   │   │       ├── WORKFLOWS_CREATION.md
│       │   │   │       ├── WORKFLOWS_REVIEW.md
│       │   │   │       ├── WORKFLOWS_UPDATE.md
│       │   │   │       ├── WORKFLOWS_TRIAGE.md
│       │   │   │       ├── WORKFLOWS_VERIFICATION.md
│       │   │   │       ├── WORKFLOWS_AGENT_DIVISION.md
│       │   │   │       ├── WORKFLOWS_PM_PR_REVIEW.md
│       │   │   │       └── POLICIES.md
│       │   │   ├── backend-development/ # default coding agent skill
│       │   │   │   └── SKILL.md
│       │   │   └── verification/        # default verifier skill
│       │   │       └── SKILL.md
│       │   └── standards.md.j2          # NEW: PM review standards (per-project)
│       │
│       └── output/                      # Output formatters
│           ├── __init__.py
│           ├── console.py               # Rich terminal output
│           └── mermaid.py               # Mermaid diagram generation (deps + concept graph)
│
└── tests/
    ├── conftest.py                      # Fixtures: tmp project dirs, sample issues, sample nodes
    ├── unit/
    │   ├── test_models.py
    │   ├── test_parser.py
    │   ├── test_reference_parser.py
    │   ├── test_store.py
    │   ├── test_node_store.py
    │   ├── test_freshness.py
    │   ├── test_validator.py
    │   ├── test_dependency_graph.py
    │   ├── test_concept_graph.py
    │   ├── test_status.py
    │   ├── test_id_generator.py
    │   ├── test_enum_loader.py          # NEW
    │   ├── test_graph_cache.py          # NEW
    │   └── test_pm_review.py            # NEW
    └── integration/
        ├── test_init.py
        ├── test_issue_lifecycle.py
        └── test_node_lifecycle.py
```

---

## Data Model

### Generated Project Directory (output of `agent-project init`)

`agent-project init` copies the entire `templates/` tree from the package into the new project, with template substitution for project name, key prefix, etc. After init, the **project repo is the source of truth** — the `agent-project` package is no longer canonical for these files. The user owns them, edits them freely, and commits them to git.

```
my-project/
├── project.yaml                    # ProjectConfig
├── CLAUDE.md                       # PM agent entry point → skill
├── enums/                          # from templates/enums/  ← all customisable enums
├── issue_templates/                # from templates/issue_templates/
├── comment_templates/              # from templates/comment_templates/
├── templates/
│   └── artifacts/                  # from templates/artifacts/  ← session output templates + manifest
├── agents/                         # from templates/agent_templates/
├── session_templates/              # from templates/session_templates/
├── orchestration/                  # from templates/orchestration/  ← patterns + Python hooks
├── .claude/
│   └── skills/                     # from templates/skills/  ← ALL skills (every agent reads from here)
│       ├── agent-messaging/
│       ├── project-manager/
│       ├── backend-development/
│       └── verification/
├── standards.md                    # from templates/standards.md.j2  ← PM review standards
├── issues/                         # One file per issue
│   └── .gitkeep
├── graph/
│   └── nodes/                      # One file per concept node
│       └── .gitkeep
├── docs/
│   └── issues/                     # Per-issue artifacts (developer.md, verified.md)
│       └── .gitkeep
├── sessions/                       # Agent session directories (see Session Artifacts section)
│   └── .gitkeep
└── .gitignore
```

**Principle: the project repo is the source of truth.** Every Enum, schema, template, skill, orchestration pattern, and rule that ships with `agent-project` is a **default reference** that gets copied into the user's project on `init`. After that, the package is no longer canonical — the project repo is. Two projects can have completely different rules for messaging, completely different artifact sets, completely different orchestration patterns, all fully under their own control and version-controlled.

**`agent-project init --update`** pulls upstream changes from the package's `templates/` into the project selectively, never overwriting user edits without confirmation. This is the upgrade path for projects that want to track new defaults as the package evolves.

`agent-project templates list` and `agent-project templates show <name>` let users explore what ships in the package without leaving the CLI.

### Enums (customisable per project)

Enums are not hardcoded Python `StrEnum` classes. They are YAML files in the project repo at `<project>/enums/<name>.yaml`, copied from packaged defaults at `templates/enums/` on `agent-project init`. After init, the project owns its enums and can add states, rename labels, recolor for the UI, or remove states it doesn't use.

The Pydantic models load enums dynamically at startup via `core/enum_loader.py`, which reads `<project>/enums/*.yaml` if present and falls back to packaged defaults otherwise.

Example enum file:

```yaml
# enums/issue_status.yaml — copied into <project>/enums/issue_status.yaml on init
name: IssueStatus
description: Issue lifecycle states
values:
  - id: backlog
    label: Backlog
    color: gray
  - id: todo
    label: To Do
    color: blue
  - id: in_progress
    label: In Progress
    color: yellow
  - id: verifying
    label: Verifying
    color: orange
  - id: reviewing
    label: Reviewing
    color: purple
  - id: testing
    label: Testing
    color: cyan
  - id: ready
    label: Ready
    color: lime
  - id: updating
    label: Updating
    color: pink
  - id: done
    label: Done
    color: green
  - id: canceled
    label: Canceled
    color: red
```

The complete set of enum files shipped under `templates/enums/`:

| File | Purpose |
|------|---------|
| `issue_status.yaml` | Issue lifecycle states |
| `priority.yaml` | Issue priority (urgent, high, medium, low) |
| `executor.yaml` | Who executes the issue (ai, human, mixed) |
| `verifier.yaml` | Whether verification is required (required, optional, none) |
| `node_type.yaml` | Concept node types (endpoint, model, config, tf_output, contract, decision, requirement, service, schema, custom) |
| `node_status.yaml` | Concept node lifecycle (active, planned, deprecated, stale) |
| `session_status.yaml` | Session lifecycle (planned, active, waiting_for_ci, …, completed, failed) |
| `re_engagement_trigger.yaml` | Why a session was re-engaged (ci_failure, plan_approved, …) |
| `message_type.yaml` | MCP message types — gains a new `status` value (see Section: Status Messages in `agent-containers.md`) |
| `agent_state.yaml` | NEW enum for status messages — see Section: Status Messages in `agent-containers.md` for the full value list (investigating, planning, awaiting_plan_approval, implementing, testing, debugging, refactoring, documenting, self_verifying, blocked, handed_off, done) |

The `AgentState` enum is brand new in this design — it powers the structured `status` message body so the UI can show "what is the agent doing right now" without parsing free-form text. Because it ships as `templates/enums/agent_state.yaml`, projects can extend it with their own states.

### Issue File Format (YAML frontmatter + Markdown body)

```yaml
# issues/PRJ-42.yaml
---
id: PRJ-42
title: Implement user authentication endpoint
status: todo
priority: high
executor: ai
verifier: required
agent: backend-api
labels:
  - domain/backend
  - env/test
parent: PRJ-8
repo: SeidoAI/web-app-backend
base_branch: test
implements:
  - REQ-AUTH-001
  - DEC-003
blocked_by:
  - PRJ-40
blocks:
  - PRJ-45
docs:
  - docs/auth/jwt-spec.md
  - docs/decisions/DEC-003.md
created_at: "2026-03-26T15:00:00"
updated_at: "2026-03-26T15:00:00"
created_by: pm-agent
---
## Context
The API needs a JWT authentication endpoint for the frontend SPA.
Must consume the [[user-model]] for credential validation and respect
the rate limiting rules in [[dec-007-rate-limiting]].

## Implements
REQ-AUTH-001, DEC-003

## Repo scope
- Repo: SeidoAI/web-app-backend
- Base branch: test
- Primary paths: src/api/auth.py, tests/unit/test_auth.py
- Required config: [[config-firebase-project-id]], [[config-jwt-secret]]

## Requirements
- POST /auth/token accepts email + password, returns JWT
- JWT expires after 1 hour
- Invalid credentials return 401 with standard error model
- Must use the [[user-firestore-schema]] for lookups

## Execution constraints
- Do not make new product/architecture decisions.
- If any ambiguity blocks correct work, stop and ask in the issue comments.

## Acceptance criteria
- [ ] Happy path returns 200 + valid JWT
- [ ] Invalid credentials return 401
- [ ] Expired token returns 403
- [ ] CI passing

## Test plan
```bash
uv run pytest tests/unit/test_auth.py -v
make lint
```

## Dependencies
PRJ-40 (Firestore user model must land first — see [[user-model]])

## Definition of Done
- [ ] Implementation complete
- [ ] Tests added/updated
- [ ] Completion comment added
- [ ] docs/issues/PRJ-42/developer.md added
- [ ] docs/issues/PRJ-42/verified.md added
- [ ] Concept nodes created/updated for new artifacts
```

Note the `[[node-id]]` references throughout the body. These are parsed by the reference parser
and resolved against the concept graph. They serve as live links to code locations that can be
validated for freshness.

**`Issue.docs: list[str] | None`** — optional doc paths from the project repo, mounted read-only into the container alongside agent-level and session-level docs. The agent definition (`agents/<id>.yaml`) declares its base `context.docs`; the issue can append issue-specific context (e.g. a JWT spec, an ADR); the session can append more on top. All three lists are merged (deduped by path) and mounted at `/workspace/docs/<path>` when the container launches.

### Concept Node File Format

Concept nodes are the core mechanism for coherence. Each node is a named, versioned pointer
to a concrete artifact in the codebase.

```yaml
# graph/nodes/auth-token-endpoint.yaml
---
id: auth-token-endpoint
type: endpoint
name: "POST /auth/token"
description: "JWT authentication endpoint - accepts email + password, returns access token"
source:
  repo: SeidoAI/web-app-backend
  path: src/api/auth.py
  lines: [45, 82]
  branch: test
  content_hash: "sha256:e3b0c44298fc1c149afbf4c8996fb924"
related:
  - user-model
  - dec-003-session-tokens
tags: [auth, api, public]
status: active
created_at: "2026-03-26T15:00:00"
updated_at: "2026-03-26T15:00:00"
created_by: claude
---
JWT authentication endpoint for the frontend SPA. Accepts email + password
credentials, validates against Firestore user collection, returns a signed
JWT with 1-hour expiry.

Response shape:
```json
{ "access_token": "eyJ...", "expires_in": 3600, "token_type": "bearer" }
```
```

**Design decisions for node files:**

- **`id` is a slug, not a UUID.** Slugs are human-readable and meaningful in `[[references]]`.
  `[[auth-token-endpoint]]` is self-documenting; `[[a1b2c3d4]]` is not. Slugs are unique
  within a project (enforced by filename = id).
- **`source` is optional.** A `planned` node doesn't point to code yet. A `decision` node
  might point to a decision document rather than code. A `config` node might just document
  an env var name without pointing to where it's read.
- **`source.lines` is optional.** For whole-file references (a model class that IS the file),
  omit lines and hash the entire file.
- **`related` lists other node IDs.** These are the node-to-node edges. Combined with the
  `[[references]]` in issue bodies (issue-to-node edges) and `blocked_by`/`blocks` in issue
  frontmatter (issue-to-issue edges), the full graph is emergent from the data.
- **The Markdown body** is optional free-form description. Useful for documenting contracts,
  response shapes, migration notes — things that don't live neatly in the code itself.

### Node type examples

**Endpoint node** — points to a route handler:
```yaml
id: auth-token-endpoint
type: endpoint
name: "POST /auth/token"
source:
  repo: SeidoAI/web-app-backend
  path: src/api/auth.py
  lines: [45, 82]
  branch: test
  content_hash: "sha256:..."
```

**Model node** — points to a data class or schema:
```yaml
id: user-model
type: model
name: "User (Firestore)"
source:
  repo: SeidoAI/web-app-backend
  path: src/models/user.py
  lines: [12, 45]
  branch: test
  content_hash: "sha256:..."
```

**Terraform output** — cross-repo infrastructure reference:
```yaml
id: tf-api-url
type: tf_output
name: "api_url (Cloud Run)"
description: "Base URL for the backend API service, consumed by frontend config"
source:
  repo: SeidoAI/web-app-infrastructure
  path: modules/cloud_run/outputs.tf
  lines: [8, 12]
  branch: test
  content_hash: "sha256:..."
related:
  - auth-token-endpoint    # this is the service that serves this URL
```

**Config node** — documents an environment variable:
```yaml
id: config-jwt-secret
type: config
name: "JWT_SECRET"
description: "HMAC signing key for JWT tokens. Must be at least 32 chars."
source:
  repo: SeidoAI/web-app-infrastructure
  path: modules/secrets/main.tf
  lines: [22, 28]
  branch: test
  content_hash: "sha256:..."
tags: [auth, secret]
```

**Contract node** — points to an API contract section:
```yaml
id: contract-auth-token
type: contract
name: "Auth Token Contract"
source:
  repo: SeidoAI/web-app-backend
  path: docs/api-contract.yaml
  lines: [120, 180]
  branch: test
  content_hash: "sha256:..."
related:
  - auth-token-endpoint    # the implementation of this contract
```

**Planned node** — placeholder for something that doesn't exist yet:
```yaml
id: refresh-endpoint
type: endpoint
name: "POST /auth/refresh"
description: "Token refresh endpoint. Will be implemented in PRJ-48."
status: planned
# No source — code doesn't exist yet
```

**Decision node** — points to a decision record (could be in the project repo itself):
```yaml
id: dec-003-session-tokens
type: decision
name: "DEC-003: Session token storage"
description: "JWT in httpOnly cookie, no localStorage. Decided for compliance."
source:
  repo: SeidoAI/web-app-backend    # or wherever the decision doc lives
  path: docs/decisions/DEC-003.md
  content_hash: "sha256:..."
status: active
```

### The edge model — all implicit, no edge files

Edges are not stored as separate files. They are **emergent from the data**:

| Edge type | Source | How it's expressed |
|-----------|--------|-------------------|
| Issue → Node | Issue body | `[[auth-token-endpoint]]` parsed from Markdown |
| Issue → Issue | Issue frontmatter | `blocked_by: [PRJ-40]` and `blocks: [PRJ-45]` |
| Issue → Requirement | Issue frontmatter | `implements: [REQ-AUTH-001]` |
| Node → Node | Node frontmatter | `related: [user-model, dec-003]` |
| Node → Source code | Node frontmatter | `source: {repo, path, lines, content_hash}` |

**Why no edge files:** Edges stored separately from their endpoints create a synchronization problem — the exact problem we're trying to solve. By keeping edges in the entities they belong to, every entity is self-describing. The full graph is reconstructed by scanning all issues and nodes.

The `agent-project graph` command and the `concept_graph.py` module build the complete graph on demand by scanning everything. For larger projects, an auto-generated index speeds up lookups (see below).

### The graph cache — incrementally maintained lookup index

**Problem**: the implicit edge model means every render needs to recompute by scanning every issue and node file. For projects with hundreds of issues this becomes slow, especially for the UI's graph view which renders constantly. Full rebuilds (`agent-project refs rebuild`) are too expensive to run on every read.

**New approach: incremental cache.** `graph/index.yaml` is committed to git as before, but it is now incrementally updated by the file watcher and CLI commands. Full rebuilds are only needed when the cache is corrupt or missing.

#### Cache schema (v2)

```yaml
# graph/index.yaml
version: 2
last_full_rebuild: "2026-04-07T10:00:00"
last_incremental_update: "2026-04-07T15:33:12"

# Per-file fingerprint — used to detect what's stale on incremental update
files:
  "issues/SEI-42.yaml":
    mtime: 1712512392
    sha: "abc123..."
    references_to: [auth-token-endpoint, user-model, dec-003]
    blocked_by: [SEI-40]
    blocks: []
  "graph/nodes/auth-token-endpoint.yaml":
    mtime: 1712510000
    sha: "def456..."
    related: [user-model]

# Computed lookup tables (the fast read paths)
by_name:
  "POST /auth/token": auth-token-endpoint

by_type:
  endpoint: [auth-token-endpoint, refresh-endpoint]
  model: [user-model]

referenced_by:
  auth-token-endpoint: [SEI-42, SEI-45]
  user-model: [SEI-40, SEI-42]

# Edges (computed once, served fast)
edges:
  - from: SEI-42
    to: auth-token-endpoint
    type: references
  - from: SEI-42
    to: SEI-40
    type: blocked_by
  - from: auth-token-endpoint
    to: user-model
    type: related

stale_nodes: []
last_freshness_check: "2026-04-07T15:00:00"
```

#### Incremental update algorithm

`agent_project/core/graph_cache.py`:

```python
def update_cache_for_file(dir, rel_path):
    """Called by file watcher on file change."""
    cache = load_index(dir)

    # Remove old edges from this file
    cache.edges = [e for e in cache.edges if e.source_file != rel_path]
    cache.files.pop(rel_path, None)

    # If file still exists, parse and re-add
    full_path = dir / rel_path
    if full_path.exists():
        if rel_path.startswith("issues/"):
            issue = load_issue(dir, key_from_path(rel_path))
            cache.files[rel_path] = fingerprint(full_path, issue)
            cache.edges.extend(issue_edges(issue))
        elif rel_path.startswith("graph/nodes/"):
            node = load_node(dir, id_from_path(rel_path))
            cache.files[rel_path] = fingerprint(full_path, node)
            cache.edges.extend(node_edges(node))

    # Rebuild lookup tables (cheap — they're derived from files dict + edges)
    cache.by_name = build_by_name(cache.files)
    cache.by_type = build_by_type(cache.files)
    cache.referenced_by = build_referenced_by(cache.edges)

    cache.last_incremental_update = now()
    save_index(dir, cache)
```

#### Who triggers updates

1. **CLI write paths** — `issue create`, `issue update`, `node create`, etc. call `update_cache_for_file()` after saving the file
2. **File watcher (UI backend)** — `watchdog` triggers `update_cache_for_file()` for any file in `issues/`, `graph/nodes/`, `sessions/`
3. **Manual** — `agent-project refs rebuild` does a full rebuild from scratch

#### Reads are now O(1)

`agent-project graph`, the UI's `/api/projects/:id/graph` endpoint, and all `refs *` commands read directly from `graph/index.yaml` without rescanning the project. The result: O(1) graph reads instead of O(N) for N issues + nodes.

#### Concurrency

A single SQLite write-ahead lock file (`graph/.index.lock`) prevents concurrent writes from corrupting the cache. Reads are unaffected (cache is just YAML).

#### Edge model unchanged

The implicit edge philosophy stays — edges are still derived from `[[references]]` in bodies and `blocked_by`/`related` in frontmatter. The cache is purely a performance layer; deleting it always rebuilds correctly. The cache is never the source of truth — it's a derived view of the underlying files.

### ProjectConfig (`project.yaml`)

```yaml
name: seido-mvp
key_prefix: SEI
description: Seido MVP project management
base_branch: test
environments: [test, prod]

# Repository registry — maps GitHub slugs to optional local paths
repos:
  SeidoAI/web-app-backend:
    local: ~/Code/seido/web-app        # optional, for fast local freshness checks
  SeidoAI/web-app-frontend:
    local: ~/Code/seido/web-app
  SeidoAI/web-app-infrastructure:
    local: ~/Code/seido/web-app
  SeidoAI/ml-business-agent:
    local: ~/Code/seido/agents/ml-business-agent

statuses:
  - backlog
  - todo
  - in_progress
  - verifying
  - reviewing
  - testing
  - ready
  - updating
  - done
  - canceled

status_transitions:
  backlog: [todo, canceled]
  todo: [in_progress, backlog, canceled]
  in_progress: [verifying, todo, canceled]
  verifying: [reviewing, in_progress]
  reviewing: [testing, in_progress]
  testing: [ready, reviewing]
  ready: [updating]
  updating: [done]
  done: []
  canceled: [backlog]

label_categories:
  executor: [ai, human, mixed]
  verifier: [required, optional, none]
  domain: []
  agent: []

# Concept graph settings
graph:
  # Node types that are valid in this project (extensible)
  node_types: [endpoint, model, config, tf_output, contract, decision, requirement, service, schema]
  # Whether to auto-rebuild index on node/issue changes
  auto_index: true

next_issue_number: 1
created_at: "2026-03-26T14:00:00"
```

### Comment Model

Comments stored as individual files in `docs/issues/<KEY>/comments/`:

```yaml
# docs/issues/PRJ-42/comments/001-start-2026-03-26.yaml
---
issue_key: PRJ-42
author: claude
type: status_change
created_at: "2026-03-26T15:30:22"
---
Starting work on PRJ-42. Created branch `claude/PRJ-42-auth-endpoint`.

No blockers. PRJ-40 merged yesterday. [[user-model]] is available in test branch.
```

Comments can also contain `[[references]]` — this is how agents document which concepts
they're working with, and it feeds the reference index.

### AgentSession Model

Sessions carry runtime state across container re-engagements. The session YAML is the
persistence anchor — it tracks what the agent has done and why it was re-engaged.

```yaml
# sessions/wave1-agent-a.yaml
---
id: wave1-agent-a
name: "Agent A: Auth + User Model"
agent: backend-coder                  # references agents/backend-coder.yaml
issues: [PRJ-40, PRJ-42]
wave: 1

# Multi-repo: every repo the session can branch and PR in. All equal, all writable.
repos:
  - repo: SeidoAI/web-app-backend
    base_branch: test
    branch: claude/SEI-40-auth          # set after first push
    pr_number: 42                       # set after PR opened
  - repo: SeidoAI/web-app-infrastructure
    base_branch: test
    branch: claude/SEI-40-tf-secrets
    pr_number: 18

# Optional session-level extra docs, merged with agent + issue docs
docs:
  - docs/integration/cross-service-flow.md

estimated_size: medium-large
blocked_by_sessions: []
key_files:
  - src/auth/
  - src/models/user.py
grouping_rationale: Same repo, tight dependency chain, overlapping files

# Session status lifecycle:
#   planned → active → waiting_for_ci → re_engaged → active → ...
#   ... → waiting_for_review → re_engaged → active → ... → completed
status: waiting_for_ci

# Latest agent state from the most recent `status` message (see Section: Status messages).
# Updated by the orchestration runtime each time a status message arrives.
current_state: implementing

# Orchestration override — pick a different pattern, or override individual fields.
# Project default lives in project.yaml; session can override either way.
orchestration:
  pattern: default                    # references orchestration/default.yaml in project repo
  overrides:
    plan_approval_required: true
    auto_merge_on_pass: false

# Artifact overrides for this session — add or remove artifacts beyond the project default
# manifest at templates/artifacts/manifest.yaml.
artifact_overrides:
  - name: architecture-diff
    file: architecture-diff.md
    template: architecture-diff.md.j2
    produced_at: completion
    required: true

# Runtime state — persisted across container restarts. Multi-repo: branch + PR live in
# the per-repo RepoBinding above; the runtime_state holds session-wide handles.
runtime_state:
  claude_session_id: "sess_abc123"    # for claude --resume
  langgraph_thread_id: null           # for langgraph checkpoint resume
  workspace_volume: "vol-wave1-a"     # Docker volume name

# Re-engagement history — append-only log
engagements:
  - started_at: "2026-03-26T14:00:00"
    trigger: initial_launch
    ended_at: "2026-03-26T16:30:00"
    outcome: pr_opened
  - started_at: "2026-03-26T17:15:00"
    trigger: ci_failure
    context: "Lint failure in src/api/auth.py:45 — ruff E302"
    ended_at: "2026-03-26T17:25:00"
    outcome: fix_pushed
---
```

**Schema notes:**

- **`repos: list[RepoBinding]`** replaces the old single `repo: str`. All repos are equal — there is no primary. The agent treats them symmetrically, can branch in any, and opens PRs against any. The session tracks one PR per repo. The `RepoBinding` model lives in `models/session.py`:

  ```python
  class RepoBinding(BaseModel):
      repo: str                            # GitHub slug
      base_branch: str
      branch: str | None = None
      pr_number: int | None = None
  ```

- **`docs: list[str] | None`** — session-level extra docs. Merged with the agent definition's `context.docs` and every issue's `docs` field, deduped by path, and mounted read-only at `/workspace/docs/<path>` in the container.

- **`current_state: str | None`** — the latest agent state from a `status` message (see the Status Messages section in `agent-containers.md`). The orchestration runtime writes this back to the session YAML each time a new status message arrives so the UI can render it without subscribing to the live stream.

- **`orchestration: { pattern: str, overrides: dict }`** — overrides for the project's default orchestration pattern. The hierarchy is **Project → Session** (just two tiers). `project.yaml` declares `orchestration.default_pattern` plus global flags; the session can either pick a different named pattern (`pattern: strict`) or override individual fields (`overrides: {plan_approval_required: true}`). Session-level fields win — straight field-level override, no deeper merging.

- **`artifact_overrides: list[ArtifactSpec]`** — per-session artifact overrides on top of the project's `templates/artifacts/manifest.yaml`. Use this to add session-specific artifacts (e.g. `architecture-diff.md`) or to mark something not required for one session.

**SessionStatus enum:**

```python
class SessionStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    WAITING_FOR_CI = "waiting_for_ci"
    WAITING_FOR_REVIEW = "waiting_for_review"
    WAITING_FOR_DEPLOY = "waiting_for_deploy"
    RE_ENGAGED = "re_engaged"
    COMPLETED = "completed"
    FAILED = "failed"

class ReEngagementTrigger(StrEnum):
    INITIAL_LAUNCH = "initial_launch"
    CI_FAILURE = "ci_failure"
    VERIFIER_REJECTION = "verifier_rejection"
    HUMAN_REVIEW_CHANGES = "human_review_changes"
    BUG_FOUND = "bug_found"
    DEPLOY_FAILURE = "deploy_failure"
    STALE_REFERENCE = "stale_reference"
    SCOPE_CHANGE = "scope_change"
    MERGE_CONFLICT = "merge_conflict"
    DEPENDENCY_CONFLICT = "dependency_conflict"
    HUMAN_RESPONSE = "human_response"
    PLAN_APPROVED = "plan_approved"
    PLAN_REJECTED = "plan_rejected"
    MANUAL = "manual"
```

### Message Log Model

Messages are delivered in real-time via HTTP (container → UI backend). But a log is
persisted in the project repo when a session completes, at `sessions/<id>/messages.yaml`.

```python
class MessageEntry(BaseModel):
    id: str
    direction: str                     # "agent_to_human" | "human_to_agent"
    type: str                          # question, plan_approval, progress, stuck, ...
    priority: str                      # blocking | informational
    author: str
    created_at: datetime
    body: str
    response: MessageResponse | None = None

class MessageResponse(BaseModel):
    author: str
    created_at: datetime
    body: str
    decision: str | None = None        # "approved" | "rejected" (for plan_approval)

class MessageLog(BaseModel):
    """Written to sessions/<id>/messages.yaml on session completion."""
    session_id: str
    messages: list[MessageEntry]
```

New session directory structure:
```
sessions/
├── wave1-agent-a.yaml               # session definition + runtime state + engagements
└── wave1-agent-a/
    ├── messages.yaml                 # message log (committed on session complete)
    └── artifacts/                    # the agent's structured outputs (see Session Artifacts)
        ├── plan.md
        ├── task-checklist.md
        ├── verification-checklist.md
        ├── recommended-testing-plan.md
        └── post-completion-comments.md
```

New CLI command:
```
agent-project session finalize <session-id>
  --messages-file TEXT   Path to messages JSON (from UI backend SQLite export)
  # Writes messages.yaml to session directory and commits to project repo.
  # Called by UI backend when session completes.
```

---

## Session Artifacts

Sessions produce structured Markdown outputs in addition to their message log. Five artifacts ship as defaults; **the set is customisable per project** via `templates/artifacts/manifest.yaml`. Projects can add, remove, or reshape artifacts. All artifacts are written by the agent to `sessions/<id>/artifacts/` in the project repo and committed via the agent's PR.

### The five default artifacts

**1. `plan.md`** — equivalent of Claude Code's plan output. Free-form Markdown produced by the agent during its planning phase. May reference `[[concept-nodes]]`. This is the candidate for plan approval gating.

**2. `task-checklist.md`** — explicit Markdown table the agent maintains as it works:

```markdown
# Task Checklist — wave1-agent-a

| # | Task | Status | Comments |
|---|------|--------|----------|
| 1 | Add JWT validation middleware | done | Used `python-jose`. See [[auth-token-endpoint]]. |
| 2 | Wire middleware into auth router | done | — |
| 3 | Add unit tests for valid/invalid/expired tokens | in_progress | Discovered an existing test fixture I can reuse. |
| 4 | Update OpenAPI contract | blocked | Waiting for contract decision from human (msg #003). |
| 5 | Add migration for `last_login` field | done | Outside scope but trivial; flagged in comment. |
```

Status values: `pending | in_progress | done | blocked | skipped`. Comments capture decisions, deviations, problems, external dependencies (in or out), or anything noteworthy.

**3. `verification-checklist.md`** — Markdown checklist the agent generates during planning and ticks off at the end:

```markdown
# Verification Checklist — wave1-agent-a

- [x] All acceptance criteria from SEI-40 met
- [x] All acceptance criteria from SEI-42 met
- [x] Unit tests pass locally (`uv run pytest`)
- [x] Lint passes (`make lint`)
- [x] No hardcoded secrets
- [x] Concept nodes created/updated for new artifacts
- [x] developer.md and verified.md drafts written
```

**4. `recommended-testing-plan.md`** — written near the end. Tells the human reviewer (and any downstream verifier agent) what should be tested manually or in higher environments, beyond what CI covers. Includes scenarios, edge cases, environment requirements, suggested commands.

```markdown
# Recommended Testing Plan — wave1-agent-a

## Manual / exploratory checks
1. Log in with a valid Firebase account; confirm JWT issued and 1-hour expiry
2. Replay an expired JWT; confirm 403 with the standard error envelope
3. Hit `/auth/token` from the frontend SPA on test env (not just curl)

## Environment-specific
- Verify `JWT_SECRET` is set in test env via `gcloud secrets versions list`
- Confirm rate limiting kicks in after 5 attempts/minute (manual)

## Regression watchlist
- Existing `/auth/refresh` should still work — not touched in this PR but shares middleware
```

**5. `post-completion-comments.md`** — written at the very end. The agent's reflective notes: decisions made, things deferred, surprises encountered, follow-ups for later. Used by the PM agent when triaging follow-up issues, and by humans during review.

```markdown
# Post-Completion Comments — wave1-agent-a

## Decisions
- Chose `python-jose` over `pyjwt` because it has built-in JWE support that we'll need for SEI-58.
- Used a constant-time comparison helper from `secrets` module instead of `==`.

## Deferred
- Did not implement `/auth/refresh` — that's SEI-48 and out of scope here.
- Did not migrate the `last_login` field on existing users; needs a one-off backfill script (suggest opening a follow-up issue).

## Surprises
- The existing `auth_middleware.py` had a stale comment claiming JWTs were stored in localStorage. They are not. Updated the comment.

## Follow-ups (suggested for PM)
- Open issue: backfill `last_login` for existing users
- Open issue: deprecate the unused `legacy_auth.py` module
```

### The artifact manifest

`templates/artifacts/manifest.yaml` declares the active artifact set and when each is produced:

```yaml
# templates/artifacts/manifest.yaml
artifacts:
  - name: plan
    file: plan.md
    template: plan.md.j2
    produced_at: planning           # planning | implementing | completion
    required: true
    approval_gate: false            # set true to enable plan approval

  - name: task-checklist
    file: task-checklist.md
    template: task-checklist.md.j2
    produced_at: planning           # initial table created at planning, updated through implementing
    required: true

  - name: verification-checklist
    file: verification-checklist.md
    template: verification-checklist.md.j2
    produced_at: planning           # generated then confirmed at completion
    required: true

  - name: recommended-testing-plan
    file: recommended-testing-plan.md
    template: recommended-testing-plan.md.j2
    produced_at: completion
    required: true

  - name: post-completion-comments
    file: post-completion-comments.md
    template: post-completion-comments.md.j2
    produced_at: completion
    required: true
```

Schema fields per artifact entry: `name`, `file`, `template`, `produced_at`, `required`, `approval_gate`.

Projects can:
- Add new artifacts (e.g. `architecture-diff.md`, `performance-notes.md`)
- Remove ones they don't need (set `required: false` or delete the entry)
- Reshape templates entirely
- Add their own `produced_at` phases if their workflow has more stages

Sessions can override via the `artifact_overrides` field on the session YAML — adding extra artifacts or marking some as not required for that specific session.

### Plan approval gate

Set `approval_gate: true` on the `plan` artifact (or any artifact) to make the agent stop after producing it and send a `plan_approval` message. The orchestrator only re-engages once approval is received. This is the mechanism by which a project (or single session) opts into human-in-the-loop plan review.

### PM agent enforcement

The PM agent's PR review (see "PM PR Review" section below) checks that all artifacts marked `required: true` in `templates/artifacts/manifest.yaml` are present before approving a session-completion PR. The skill instructions for coding agents tell them to read `templates/artifacts/manifest.yaml` to know what they must produce.

---

## Core Module Responsibilities

### `core/parser.py` — Frontmatter + Body Parser
- Split file on `---` delimiter: YAML frontmatter → structured fields, Markdown body → `body` field
- Round-trip: serialize model back to frontmatter + body format
- Handle edge cases (no body, no frontmatter, body-only)
- Used by both issues and concept nodes (same file format)

### `core/store.py` — Issue & Project CRUD
- `load_project(dir) -> ProjectConfig`
- `save_project(dir, config)`
- `load_issue(dir, key) -> Issue`
- `save_issue(dir, issue)`
- `list_issues(dir, filters) -> list[Issue]`
- `next_key(dir) -> str` (auto-increment from project.yaml)
- `load_comments(dir, key) -> list[Comment]`
- `save_comment(dir, comment)`

### `core/node_store.py` — Concept Node CRUD + Index
- `load_node(dir, id) -> ConceptNode`
- `save_node(dir, node)` — writes to `graph/nodes/<id>.yaml`
- `list_nodes(dir, type_filter, status_filter) -> list[ConceptNode]`
- `delete_node(dir, id)`
- `rebuild_index(dir)` — scan all issues + nodes, build `graph/index.yaml`
- `load_index(dir) -> GraphIndex`
- `resolve_name(dir, name) -> str | None` — name → node ID lookup

### `core/reference_parser.py` — Extract `[[references]]` from Markdown
- Parse `[[node-id]]` patterns from any Markdown body (issues, comments, nodes)
- Return list of referenced node IDs
- Handle edge cases: broken references, nested brackets, code blocks (don't parse inside code fences)
- Provide `replace_references(body, resolver)` for rendering references with links (for UI phase later)

### `core/freshness.py` — Content Hashing + Staleness Detection

This is the core coherence mechanism. It answers: "has the code that this node points to changed?"

- `hash_content(content: str) -> str` — SHA-256 hash of content string
- `fetch_content(source: NodeSource, project: ProjectConfig) -> str | None`
  - Check if repo has a configured local path in `project.yaml`
  - If local: read file, extract lines if specified
  - If not local: use `gh api repos/{owner}/{repo}/contents/{path}?ref={branch}` via GitHub API
  - Return the content string, or None if file not found
- `check_node_freshness(node: ConceptNode, project: ProjectConfig) -> FreshnessResult`
  - Fetch current content
  - Hash it
  - Compare to `node.source.content_hash`
  - Return: `fresh | stale | source_missing | no_source`
- `check_all_nodes(dir) -> list[FreshnessResult]`
  - Batch check all active nodes with sources
  - Report: fresh count, stale count, missing count, details
- `rehash_node(node: ConceptNode, project: ProjectConfig) -> ConceptNode`
  - Fetch current content, compute new hash, update node

**Why local + GitHub API:**
- Local clone is fast (no network, no rate limits). Use it when available.
- GitHub API is the fallback for repos that aren't cloned locally. The `gh` CLI handles auth.
- `project.yaml` maps repo slugs to local paths. This is optional — if no local path is configured, the system uses the GitHub API.

```python
# core/freshness.py — resolution logic

def fetch_content(source: NodeSource, project: ProjectConfig) -> str | None:
    """Fetch content from local clone or GitHub API."""
    repo_config = project.repos.get(source.repo)
    local_path = repo_config.local if repo_config else None

    if local_path:
        expanded = Path(local_path).expanduser()
        if expanded.exists():
            return _read_local(expanded / source.path, source.lines)

    # Fall back to GitHub API
    return _fetch_github(source.repo, source.path, source.lines, source.branch)


def _read_local(file_path: Path, lines: tuple[int, int] | None) -> str | None:
    """Read content from a local file, optionally extracting a line range."""
    if not file_path.exists():
        return None
    text = file_path.read_text(encoding="utf-8")
    if lines:
        file_lines = text.splitlines()
        start, end = lines[0] - 1, lines[1]  # 1-indexed to 0-indexed
        return "\n".join(file_lines[start:end])
    return text


def _fetch_github(repo: str, path: str, lines: tuple[int, int] | None, branch: str) -> str | None:
    """Fetch file content via GitHub API using `gh` CLI."""
    import subprocess
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{path}", "-q", ".content", "--jq", ".content"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    # GitHub API returns base64-encoded content
    import base64
    content = base64.b64decode(result.stdout.strip()).decode("utf-8")
    if lines:
        file_lines = content.splitlines()
        start, end = lines[0] - 1, lines[1]
        return "\n".join(file_lines[start:end])
    return content
```

### `core/validator.py` — Issue Quality Checks (ported from `validate_agent_issue.py`)
- Check required Markdown headings in body (Context, Implements, Repo scope, Requirements, Acceptance criteria, Test plan, Dependencies, Definition of Done)
- Check "stop and ask" guidance present
- Validate executor/verifier label consistency
- Validate dependency references exist (issue keys)
- **Validate `[[references]]` resolve to existing nodes**
- **Report stale references (nodes whose content_hash is outdated)**
- Warn on placeholder keys (`ISS-\d+`)
- Return structured `ValidationResult` with errors/warnings/stale_refs
- **Validate session status transitions** (e.g., can't go from `planned` to `completed` directly)
- **Warn on sessions stuck in waiting states** (e.g., `waiting_for_ci` for >1 hour with no CI run)
- **Validate session agent references** (agent ID in session must match an `agents/<id>.yaml` file)

### `core/dependency_graph.py` — Issue Dependency Graph (ported from `dependency_graph.py`)
- Build graph from `list[Issue]` (not raw JSON — cleaner input)
- Cycle detection (existing DFS algorithm)
- Critical path computation (existing longest-path DP)
- Mermaid output (enhanced: color nodes by status)
- Graphviz DOT output
- Return `DependencyGraphResult` model

### `core/concept_graph.py` — Full Unified Graph

This builds the complete graph that includes everything: issues, concept nodes, and all edges.
This is what the UI will visualize later.

- `build_full_graph(dir) -> FullGraphResult`
  - Load all issues
  - Load all concept nodes
  - Extract all `[[references]]` from issue bodies
  - Extract all `blocked_by`/`blocks` edges from issue frontmatter
  - Extract all `related` edges from node frontmatter
  - Extract all `source` edges from nodes to code locations
  - Return unified graph with typed nodes and typed edges
- `to_mermaid(graph, filter) -> str` — Render as Mermaid with node-type coloring
- `orphan_nodes(graph) -> list[str]` — Nodes not referenced by any issue
- `orphan_issues(graph) -> list[str]` — Issues with no node references (potential coherence gap)

### `core/status.py` — Status Transitions & Dashboard
- Validate transitions against `project.yaml` rules
- Aggregate counts by status, executor, priority
- Identify blocked issues, stale issues (issues referencing stale nodes)
- Compute critical path summary

### `core/id_generator.py` — Key Generation
- Read `next_issue_number` from project.yaml
- Generate `<PREFIX>-<N>` (e.g., `SEI-42`)
- Atomically increment counter

### `core/enum_loader.py` — Dynamic Enum Loading
- `load_enums(project_dir) -> dict[str, Enum]` — read every YAML file under `<project>/enums/`, build a `StrEnum` for each, fall back to packaged defaults from `templates/enums/` for any enum not present in the project
- Pydantic models import their enums via this loader at module init time so projects can extend `IssueStatus`, `AgentState`, `MessageType`, etc., without forking the package

### `core/graph_cache.py` — Incremental Graph Index
- See the "Graph cache" section below for the v2 schema and the `update_cache_for_file` algorithm
- `load_index(dir) -> GraphIndex`, `save_index(dir, cache)`, `update_cache_for_file(dir, rel_path)`, `full_rebuild(dir)`
- Uses a SQLite write-ahead lock file (`graph/.index.lock`) to keep concurrent writes from corrupting the cache

### `core/pm_review.py` — PM Agent PR Review Checks
- See the "PM PR Review" section below for the full check list
- Each check is a function returning `CheckResult(name, passed, details, fix_hint)`
- Run by `agent-project pm review-pr <pr-number>` against the diff of a project-repo PR

---

## Orchestration Patterns

Orchestration patterns codify *who acts when*: PM auto-launches vs human approves, plan gate enabled or not, verifier required or skipped, auto-merge on green, etc. Different projects and sessions need different patterns. The patterns themselves are project-owned YAML (with optional Python hook scripts as an escape hatch), version-controlled in the project repo.

**Important: the orchestration runtime lives in `agent-containers`, not `agent-project`.** The runtime is the engine that reads patterns and dispatches actions on every event. The `agent-project` package owns the data models, the templates that ship as defaults, and the CLI for managing patterns. This matches the broader principle: the project repo is the configuration; `agent-containers` is the engine that executes that configuration. The runtime reads from the project repo on every event.

### File layout

```
my-project/
├── orchestration/
│   ├── default.yaml          # project default pattern (used unless overridden)
│   ├── strict.yaml           # named alternative (max human gates)
│   ├── fast.yaml             # named alternative (auto-everything)
│   └── hooks/                # Python hook scripts (optional escape hatch)
│       ├── __init__.py
│       └── custom_verifier.py
```

These are copied from `templates/orchestration/` on `agent-project init`. After init the project owns them — edit, add, remove freely.

### YAML rule format

```yaml
# orchestration/default.yaml
name: default
description: Standard project default — PM auto-orchestrates with human gates only on plan approval

events:
  session_started:
    actions:
      - require_artifact: plan.md
      - if: project.plan_approval_required
        then:
          - send_message: { type: plan_approval, priority: blocking }
          - wait_for: human_response
        else:
          - continue

  plan_approved:
    actions:
      - re_engage: { trigger: plan_approved }

  ci_failure:
    actions:
      - re_engage: { trigger: ci_failure, context_from: ci_logs }

  pr_opened:
    actions:
      - launch_agent: verifier
      - on_verifier_pass:
          - if: project.auto_merge_on_pass
            then: [ merge_pr ]
            else: [ notify_human ]
      - on_verifier_fail:
          - re_engage: { trigger: verifier_rejection, context_from: verifier_review }

  human_review_changes:
    actions:
      - re_engage: { trigger: human_review_changes, context_from: pr_comments }

  status_message_received:
    actions:
      - update_session_status_summary: { from: message }

  artifact_updated:
    when: artifact == "task-checklist.md"
    actions:
      - publish_to_ui

# Optional: call out to a Python hook for complex logic
hooks:
  pre_re_engage: hooks.custom_verifier.maybe_skip_verifier
```

### Built-in actions (the action vocabulary)

| Action | Effect |
|--------|--------|
| `re_engage` | Calls `agent-project session re-engage` + `agent-containers launch` |
| `launch_agent` | Spawns a new container for a named agent (e.g. verifier) |
| `send_message` | Posts to UI message inbox |
| `wait_for` | Pauses the orchestrator until an event happens |
| `merge_pr` | `gh pr merge` |
| `notify_human` | UI desktop notification |
| `require_artifact` | Asserts the agent has produced a named artifact |
| `update_session_status_summary` | Writes status state + summary back to session.yaml |
| `publish_to_ui` | Broadcasts an event over WebSocket |
| `if/then/else` | Conditional branch on `project.<field>` or `session.<field>` |

### Hook scripts (Python escape hatch)

Hooks live in `<project>/orchestration/hooks/*.py` and are invoked by name from the YAML. Signature:

```python
# orchestration/hooks/custom_verifier.py
from agent_project.orchestration import Event, Context

def maybe_skip_verifier(event: Event, ctx: Context) -> dict:
    """Skip verifier for trivial PRs (e.g. only docs changed)."""
    if all(f.endswith('.md') for f in ctx.pr_files):
        return {"skip": True}
    return {"skip": False}
```

The hook receives the event and a context object (session, PR, message, etc.) and returns a dict the orchestrator merges into its decision state.

### Hierarchy: Project → Session

Just two tiers — no agent-tier or issue-tier overrides. This keeps the mental model simple: there is a project default, and any session may override it.

Project default (in `project.yaml`):

```yaml
# project.yaml
orchestration:
  default_pattern: default       # references orchestration/default.yaml
  plan_approval_required: false  # global default
  auto_merge_on_pass: false      # global default
```

Session override: a session can pick a different pattern OR override individual fields.

```yaml
# sessions/wave1-agent-a.yaml
orchestration:
  pattern: strict                # use orchestration/strict.yaml instead
  # OR override individual fields:
  overrides:
    plan_approval_required: true
    auto_merge_on_pass: false
```

Session-level fields *win* over project-level fields. No deeper merging — straight field-level override.

### Example session that overrides

```yaml
# sessions/critical-prod-fix.yaml — wants extra gates
orchestration:
  pattern: default
  overrides:
    plan_approval_required: true     # require human approval before code
    auto_merge_on_pass: false        # no auto-merge even if CI green
```

### Where the orchestration runtime runs

The runtime module (`agent_containers/core/orchestration.py`) reacts to events from:
- File watcher on the project repo (issue/session/artifact changes)
- WebSocket messages (agent status updates from running containers)
- GitHub webhook polling (CI status, PR reviews)
- MCP messages from agents (plan ready, status updates, blocking questions)

It exposes:
- `load_pattern(project_dir, name)` — reads `<project>/orchestration/<name>.yaml`
- `merge_overrides(pattern, session)` — applies session-level overrides on top of project default
- `evaluate_event(pattern, event, ctx)` — looks up matching event in the YAML, evaluates conditions, returns action list
- `run_action(action, ctx)` — executes a built-in action (re_engage, launch_agent, etc.)
- `call_hook(hook_name, event, ctx)` — invokes a Python hook from `<project>/orchestration/hooks/`

The PM agent is a Claude-driven container that can also call into the orchestrator (via the agent-project CLI or directly) for higher-level reasoning. The deterministic orchestrator handles the simple event → action flows; the PM agent handles judgement-heavy decisions (plan review, scope changes, conflict resolution).

`agent-project orchestrate evaluate <event-file>` lets users dry-run an event against the project's patterns from the command line — useful for debugging.

---

## PM PR Review

Coding agents push PRs to *target repos* (web-app-backend, etc.) AND PRs to the *project repo* (containing updates to issues, sessions, nodes, comments, artifacts). The PM agent's job is to review the project-repo PRs.

### What the PM agent checks

When a coding agent opens a PR to the project repo, the PM agent runs the following checks via `core/pm_review.py`. Each check is a function returning `CheckResult(name, passed, details, fix_hint)`.

1. **Schema validation** — every changed YAML file passes pydantic validation (using the project's loaded enums)
2. **Reference integrity** — all `[[node-id]]` references in changed files resolve to existing nodes
3. **Status transition validity** — issue/session status transitions match `project.yaml` rules
4. **Required-fields check** — issues have all required frontmatter (executor, verifier, repo, etc.)
5. **Markdown structure** — issue bodies have all required sections (Context, Acceptance criteria, etc.)
6. **Concept node freshness** — newly added/edited nodes have valid `source` (file exists, hash computed)
7. **Artifact presence** — sessions in `completed` state have all artifacts marked `required: true` in `templates/artifacts/manifest.yaml` (default set: `plan.md`, `task-checklist.md`, `verification-checklist.md`, `recommended-testing-plan.md`, `post-completion-comments.md`)
8. **No orphan additions** — new nodes are referenced by at least one issue or marked `planned`
9. **Comment provenance** — new comments have valid author + type
10. **Project standards** — rules in `<project>/standards.md` (free-form Markdown rules — generated from `templates/standards.md.j2` on init)

The artifact-presence check (#7) reads `templates/artifacts/manifest.yaml` from the project repo, so it automatically respects per-project customisation: if a project removed `recommended-testing-plan.md` from its manifest, the PM does not require it.

If all pass: PM posts an approval review on the PR. If `auto_merge_on_pass` is enabled in orchestration, the PM merges.

If any fail: PM posts a `request_changes` review with specific feedback per check, and the orchestrator re-engages the coding agent with the failing checks as context.

### CLI

```
agent-project pm review-pr <pr-number>
  --repo TEXT          Project repo (GitHub slug) [required]
  --format TEXT        rich/json [default: rich]
  # Runs all 10 checks against the diff. Prints results. Returns nonzero on failures.
  # The PM agent (containerised or not) calls this.
```

---

## CLI Commands

### Issue management

```
agent-project init <name>
  --key-prefix TEXT    Issue key prefix (e.g., SEI, PRJ)
  --base-branch TEXT   Default base branch [default: test]
  --repos TEXT         Comma-separated repo list (GitHub slugs)
  --no-git             Skip git init
  --update             Pull upstream template changes into an existing project
                       without overwriting user edits (interactive on conflict)

agent-project issue create
  --title TEXT         Issue title (required)
  --executor TEXT      ai/human/mixed [default: ai]
  --verifier TEXT      required/optional/none [default: required]
  --priority TEXT      urgent/high/medium/low [default: medium]
  --parent TEXT        Parent epic key
  --repo TEXT          Target repo
  --blocked-by TEXT    Comma-separated blocking issue keys
  --labels TEXT        Comma-separated labels
  --template TEXT      Body template to use [default: default]

agent-project issue list
  --status TEXT        Filter by status(es)
  --executor TEXT      Filter by executor type
  --label TEXT         Filter by label
  --parent TEXT        Filter by parent epic
  --format TEXT        table/json/yaml [default: table]

agent-project issue show <key>
  --format TEXT        rich/json/yaml [default: rich]

agent-project issue update <key>
  --status TEXT        New status (validated against transitions)
  --title TEXT         New title
  --priority TEXT      New priority
  --add-label TEXT     Add label
  --remove-label TEXT  Remove label

agent-project issue validate [key]
  --strict             Treat warnings as errors
  --check-refs         Also check freshness of referenced nodes [default: true]
```

### Concept graph

```
agent-project node create
  --id TEXT            Node slug ID (required, must be unique)
  --type TEXT          Node type: endpoint/model/config/tf_output/contract/decision/... (required)
  --name TEXT          Human-readable name (required)
  --repo TEXT          Source repo (GitHub slug)
  --path TEXT          File path within repo
  --lines TEXT         Line range, e.g. "45-82"
  --branch TEXT        Branch to track [default: project base_branch]
  --related TEXT       Comma-separated related node IDs
  --tags TEXT          Comma-separated tags
  --status TEXT        active/planned/deprecated [default: active]
  # If --repo and --path provided, content is fetched and hashed automatically

agent-project node list
  --type TEXT          Filter by node type
  --status TEXT        Filter by status
  --stale              Only show stale nodes
  --format TEXT        table/json/yaml [default: table]

agent-project node show <id>
  --format TEXT        rich/json/yaml [default: rich]

agent-project node check [id]
  # If id provided: check one node. Otherwise: check all active nodes with sources.
  # Fetches current content (local or GitHub API), hashes, compares.
  # Reports: fresh / stale / source_missing for each node.
  --update             Automatically rehash stale nodes (update content_hash + updated_at)
  --format TEXT        table/json [default: table]

agent-project node update <id>
  --path TEXT          Update source file path (e.g., code moved)
  --lines TEXT         Update line range
  --repo TEXT          Update source repo
  --rehash             Fetch current content and update hash
  --status TEXT        Update status (active/planned/deprecated/stale)
  --add-related TEXT   Add related node IDs
  --remove-related TEXT Remove related node IDs
```

### Reference tracking

```
agent-project refs list <issue-key>
  # Show all [[references]] in this issue and their freshness status

agent-project refs reverse <node-id>
  # Show all issues that reference this node

agent-project refs check
  # Full scan: find all references across all issues, check freshness of all
  # referenced nodes, report stale references and orphan nodes
  --format TEXT        table/json [default: table]

agent-project refs rebuild
  # Rebuild the graph/index.yaml from scratch by scanning all issues + nodes
```

### Status and graphs

```
agent-project status
  --format TEXT        rich/json [default: rich]
  # Now includes: stale reference count, orphan node count

agent-project graph
  --format TEXT        mermaid/dot [default: mermaid]
  --output TEXT        Output file path
  --type TEXT          deps (issue dependencies only) / concept (full graph) [default: deps]
  --status-filter TEXT Only include issues with these statuses

agent-project session create
  --name TEXT          Session name
  --agent TEXT         Agent definition ID (references agents/<id>.yaml)
  --issues TEXT        Comma-separated issue keys
  --wave INT           Wave number

agent-project session list
  --status TEXT        Filter by status (planned, active, waiting_for_ci, etc.)
  --wave INT           Filter by wave number
  --format TEXT        table/json [default: table]

agent-project session show <session-id>
  --format TEXT        rich/json/yaml [default: rich]
  # Shows full session detail including engagement history

agent-project session re-engage <session-id>
  --trigger TEXT       Trigger type: ci_failure, verifier_rejection, human_review_changes,
                       bug_found, deploy_failure, stale_reference, scope_change,
                       merge_conflict, dependency_conflict, manual (required)
  --context TEXT       Freeform context string (error output, review comments, etc.)
  --context-file TEXT  Read context from a file (for long CI output, etc.)
  # Appends a new engagement entry to the session, sets status to re_engaged.
  # Used by GitHub Actions and PM agent to trigger re-engagement.

agent-project session update <session-id>
  --status TEXT        Update status (e.g., waiting_for_ci, completed, failed)
  --branch TEXT        Update branch name
  --pr-number INT      Update PR number
  --claude-session TEXT  Update Claude session ID
  --langgraph-thread TEXT  Update LangGraph thread ID
  --volume TEXT        Update Docker volume name
```

### PM PR review

```
agent-project pm review-pr <pr-number>
  --repo TEXT          Project repo (GitHub slug) [required]
  --format TEXT        rich/json [default: rich]
  # Runs all 10 PM checks against the project-repo PR diff. Prints results.
  # Returns nonzero on failures. Used by the PM agent and CI.
```

### Orchestration

```
agent-project orchestrate evaluate <event-file>
  --pattern TEXT       Pattern name (default: project's default_pattern)
  --session TEXT       Session ID (for override evaluation)
  # Dry-run an event against the project's orchestration patterns.
  # Reads <event-file> as JSON, prints the resulting action list.
```

### Templates, enums, artifacts

```
agent-project templates list
  # List all template files shipped with the package and their target locations
  # in the project repo.

agent-project templates show <name>
  # Print the contents of a packaged template (e.g. plan.md.j2).

agent-project enums list
  # List the active enums in this project (loaded from <project>/enums/ if present,
  # else from packaged defaults).

agent-project enums show <name>
  # Print the values of an enum (e.g. issue_status, agent_state).

agent-project artifacts list <session-id>
  # List the artifacts produced (or expected) for a session, based on the
  # active manifest.yaml + any session-level artifact_overrides.

agent-project artifacts show <session-id> <artifact-name>
  # Print the contents of a session artifact.
```

---

## Key Files to Reuse / Port

| Source | Target | Notes |
|--------|--------|-------|
| `ide-config/.../scripts/dependency_graph.py` (258 lines) | `core/dependency_graph.py` | Port cycle detection, critical path, Mermaid/DOT output. Change input from JSON to `list[Issue]` |
| `ide-config/.../scripts/validate_agent_issue.py` (62 lines) | `core/validator.py` | Port required headings check, placeholder detection. Add label validation, dependency validation, reference validation |
| `ide-config/.../assets/templates/linear_issue_body.md` | `templates/issue_templates/default.yaml.j2` | Convert from Linear template to YAML frontmatter + body format. Add `[[reference]]` guidance |
| `ide-config/.../SKILL.md` + references/ | `templates/skills/` | Adapt PM agent skill from Linear-based to git-native. Add concept graph maintenance to update workflow |
| `ide-config/.../assets/policies/` | `templates/skills/references/POLICIES.md` | Bundle policies into single reference doc |
| `ml-business-agent/pyproject.toml` | `pyproject.toml` | Follow same conventions: hatchling, ruff, dependency-groups |

---

## Dependencies

```toml
[project]
name = "agent-project"
version = "0.1.0"
description = "Git-native project management with concept graph for AI agents"
requires-python = ">=3.10,<3.14"
dependencies = [
    "pydantic>=2.0,<3.0",
    "click>=8.1,<9.0",
    "pyyaml>=6.0,<7.0",
    "rich>=13.0,<14.0",
    "jinja2>=3.1,<4.0",
]

[project.scripts]
agent-project = "agent_project.cli.main:cli"

[dependency-groups]
dev = [
    "pytest>=8.0,<9.0",
    "ruff>=0.4.6,<1.0",
    "codespell>=2.2,<3.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agent_project"]

[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "C", "B", "UP", "RUF"]
ignore = ["E501", "C901", "B006"]

[tool.ruff.lint.isort]
known-first-party = ["agent_project"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.codespell]
skip = "uv.lock,.venv"
```

Note: no `gitpython` dependency. Git operations use `subprocess.run(["git", ...])` for simplicity.
GitHub API access uses `subprocess.run(["gh", ...])`. Both `git` and `gh` are expected to be
available in the environment (reasonable for a developer/agent tool).

---

## Implementation Steps

### Step 1: Package scaffold
- Create `pyproject.toml`, `Makefile`, `src/agent_project/__init__.py`
- Set up ruff, pytest config
- Verify `uv sync` and `uv run pytest` work

### Step 2: Enums and core models
- `models/enums.py` — all StrEnum types (IssueStatus, Priority, Executor, Verifier, NodeType, NodeStatus)
- `models/project.py` — ProjectConfig (including `repos` with local paths, `graph` settings)
- `models/issue.py` — Issue (frontmatter fields + body)
- `models/node.py` — ConceptNode, NodeSource (the concept graph node model)
- `models/comment.py` — Comment
- `models/session.py` — AgentSession, Wave
- `models/graph.py` — DependencyGraphResult, FreshnessResult, FullGraphResult, GraphIndex
- Unit tests for model validation, serialization round-trips

### Step 3: Parser, reference parser, and stores
- `core/parser.py` — YAML frontmatter + Markdown body parser/serializer
- `core/reference_parser.py` — `[[node-id]]` extraction from Markdown bodies
- `core/store.py` — File-based CRUD for issues, project config, comments
- `core/node_store.py` — File-based CRUD for concept nodes, index rebuild
- `core/id_generator.py` — Auto-increment keys
- Unit tests for parsing, reference extraction, store operations, key generation

### Step 4: Freshness, validator, and dependency graph
- `core/freshness.py` — Content hashing, local + GitHub API fetching, staleness detection
- `core/validator.py` — Port from `validate_agent_issue.py`, add reference validation
- `core/dependency_graph.py` — Port from `dependency_graph.py`, accept `list[Issue]`
- `core/concept_graph.py` — Full unified graph builder
- `core/status.py` — Transition validation, dashboard aggregation (including staleness)
- `output/mermaid.py` — Mermaid diagram generation (deps + concept graph)
- Unit tests for hashing, freshness checking, validation, graph analysis

### Step 5: CLI — init command
- `cli/main.py` — Click group, global `--project-dir` option
- `cli/init.py` — `agent-project init` generates full project scaffold (including `graph/nodes/`)
- `templates/` — All Jinja2 templates and static files for init
- Port and adapt SKILL.md + workflow references from linear-project-manager (add graph maintenance)
- Integration test: init creates valid project, git repo works

### Step 6: CLI — issue commands
- `cli/issue.py` — create, list, show, update, validate
- `output/console.py` — Rich tables, detail views (show `[[references]]` with freshness indicators)
- Integration test: full issue lifecycle (create → update → validate → list)

### Step 7: CLI — node and refs commands
- `cli/node.py` — create, list, show, check, update
- `cli/refs.py` — list, reverse, check, rebuild
- Integration test: node lifecycle (create → reference in issue → check freshness → update)

### Step 8: CLI — status, graph, session commands
- `cli/status.py` — Dashboard with status breakdown, blocked issues, stale refs, critical path
- `cli/graph.py` — Dependency graph + concept graph output
- `cli/session.py` — Agent session CRUD
- Integration tests

### Step 9: Polish
- Error messages, help text, edge cases
- Ensure `pip install .` and `agent-project --help` work
- Ensure `pip install git+https://github.com/...` works

---

## Verification

1. **Unit tests**: `uv run pytest tests/unit/ -v` — all model validation, parsing, store, graph, validator, freshness tests pass
2. **Integration tests**: `uv run pytest tests/integration/ -v` — init flow, issue lifecycle, node lifecycle
3. **Manual smoke test**:
   ```bash
   cd /tmp && agent-project init test-project --key-prefix TST
   cd test-project

   # Issue CRUD
   agent-project issue create --title "First issue" --executor ai --priority high
   agent-project issue create --title "Second issue" --blocked-by TST-1
   agent-project issue list
   agent-project issue validate
   agent-project issue update TST-1 --status in_progress

   # Concept graph
   agent-project node create --id auth-endpoint --type endpoint --name "POST /auth/token" \
     --repo SeidoAI/web-app-backend --path src/api/auth.py --lines "45-82"
   agent-project node list
   agent-project node show auth-endpoint
   agent-project node check          # checks freshness of all nodes

   # References (after adding [[auth-endpoint]] to an issue body)
   agent-project refs list TST-1
   agent-project refs reverse auth-endpoint
   agent-project refs check          # full staleness scan

   # Dashboard and graph
   agent-project status
   agent-project graph --type deps --format mermaid
   agent-project graph --type concept --format mermaid
   ```
4. **Lint**: `uv run ruff check src/ tests/`
5. **Package install**: `pip install .` from the repo root, then `agent-project --help` works
