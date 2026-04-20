# Tripwire v0.7 — unified design

**Status**: approved design
**Date**: 2026-04-20
**Supersedes**:
- `2026-04-16-v07-pm-monitor.md`
- `2026-04-17-v07-issue-developer-notes.md`

**Summary**: Major release. Renames the project from `keel` to `tripwire`
(v0.7a), then ships the full PM session lifecycle (monitor, review,
complete), per-issue artifact enforcement, spawn refinements, CI
infrastructure, and vocabulary alignment (all v0.7b).

---

## 1. Context

After v0.6c we can spawn local sessions in worktrees, compute dependency
agendas, and track session lifecycle. But the PM workflow is incomplete:

- PM goes idle after spawn; no structured way to monitor executing agents.
- No tool to review PR diffs against issue specs.
- No end-of-lifecycle command (close issues, reconcile nodes, clean up).
- Spawn invocation leaves quality on the table (no `--effort max`,
  no `--model opus`, no cost cap, no session naming for resume).
- Every PR review has flagged missing `developer.md` / `verified.md` —
  the DoD checklist asks for them, but nothing enforces them.
- Session phase vocabulary (`implementing`/`verifying`/`completion`)
  and issue status vocabulary (`in_progress`/`in_review`/`done`) mean
  the same things but use different words.
- Neither the tripwire repo nor the projects it manages have any CI.
- The name `keel` is overloaded in the Python ecosystem and collides
  with multiple adjacent libraries.

v0.7 closes all of this.

## 2. Scope summary

Eight feature areas. v0.7a is the rename (prerequisite). v0.7b is
everything else, released together.

| § | Feature | Phase |
|---|---|---|
| 3 | Rename `keel` → `tripwire` | v0.7a |
| 4 | Vocabulary alignment (ArtifactPhase ↔ IssueStatus) | v0.7b Phase 1 |
| 5 | Per-issue artifacts (developer.md, verified.md enforced) | v0.7b Phase 2 |
| 6 | Spawn refinements (Claude Code flags, spawn_config) | v0.7b Phase 3 |
| 7 | Session monitor (`/pm-session-monitor`) | v0.7b Phase 4 |
| 8 | Session review (`/pm-session-review`) | v0.7b Phase 5 |
| 9 | Session complete (`/pm-session-complete`) | v0.7b Phase 6 |
| 10 | CI + PyPI publishing + project workflow templates | v0.7b Phases 7-8 |

**Non-goals for v0.7:**
- Real verification agent (PM acts as verifier, writes `verified.md`)
- Agent messaging MCP (monitor uses stream-json only)
- Container-aware monitoring
- Auto-remediation by default (read-only automation; per-command
  overrides via slash args)
- Multi-project workspace monitor
- Per-issue `artifact_overrides` field on issue.yaml
- Grandfather clauses or legacy vocabulary aliases (clean cut)

---

## 3. v0.7a — Rename to `tripwire`

### 3.1 Rationale

Core mechanism: inject post-validation warnings into the agent's most
recent context (LLMs over-weight recency). That's a tripwire.

The current name `keel` is overloaded with adjacent libraries (AI agents
routinely hallucinate keel-named packages). Renaming now, before any
PyPI publish, is cheap because downstream = only our 3 test projects.

### 3.2 Changes

| Layer | Before | After |
|---|---|---|
| Package name | `keel` | `tripwire` |
| CLI commands | `keel <subcommand>` | `tripwire <subcommand>` AND `tw <subcommand>` (alias) |
| Import path | `from keel.core import ...` | `from tripwire.core import ...` |
| Repo name | `SeidoAI/keel` | `SeidoAI/tripwire` (GitHub redirects preserved) |
| Config field | `project.yaml.keel_version` | `project.yaml.tripwire_version` |
| Lock file | `.keel.lock` | `.tripwire.lock` |
| Hidden dir | `.keel/merge-briefs/` | `.tripwire/merge-briefs/` |
| Log dir | `~/.keel/logs/` | `~/.tripwire/logs/` |
| Workspace field | `keel_version` on `Workspace` | `tripwire_version` |
| Agent/PM skill refs | "keel" in prose | "tripwire" |
| Slash commands | `/pm-*` (unaffected) | `/pm-*` (unaffected) |

### 3.3 CLI entry points

`pyproject.toml` declares both console scripts:

```toml
[project.scripts]
tripwire = "tripwire.cli.main:cli"
tw = "tripwire.cli.main:cli"
```

`tripwire` is canonical in all docs. `tw` is the ergonomic alias
(matches `gh`, `uv`, `rg`, `cc` patterns).

### 3.4 Test projects

All three (`kb-pivot`, `graph-ui-v2`, `project-keel-ui-init`) get a
migration PR that updates `project.yaml` (field rename) and any
docs/comments mentioning `keel`. The `project-keel-ui-init` directory
itself is not renamed — users can rename their projects independently.

### 3.5 Open risk

PyPI `tripwire` availability — checked as free at time of drafting
but must be re-confirmed during Phase 7. Fallback: `tripwire-pm`.

---

## 4. Vocabulary alignment (v0.7b Phase 1)

### 4.1 The rename

`ArtifactPhase` values align with `IssueStatus` values:

```python
# before
ArtifactPhase = Literal["planning", "implementing", "verifying", "completion"]

# after
ArtifactPhase = Literal["planning", "in_progress", "in_review", "done"]
```

`planning` stays — there's no issue analog (issues skip planning; the
PM plans them into existence once per session).

### 4.2 Clean cut (no aliases)

Every manifest YAML, session YAML, fixture, skill doc, and reference
gets rewritten in one migration pass. No legacy alias layer at load
time. Rationale: we have three test projects, the rename is mechanical,
adding transitional plumbing is more code to remove later.

Files touched:
- `src/tripwire/models/manifest.py` — `ArtifactPhase` literal
- `src/tripwire/templates/artifacts/manifest.yaml` — every `produced_at`
- `src/tripwire/core/validator.py` — phase references in messages
- `src/tripwire/templates/skills/**/*.md` — vocabulary in skill docs
- All session YAMLs in test fixtures and test projects
- `docs/**.md`

### 4.3 Layer 2: enum-coherence test

Prevents regression at CI time:

```python
SESSION_ONLY_PHASES: frozenset[str] = frozenset({"planning"})

def test_artifact_phases_align_with_issue_status():
    overlap_required = set(ArtifactPhase) - SESSION_ONLY_PHASES
    assert overlap_required.issubset(set(IssueStatus))
```

Fails if anyone adds a new phase that doesn't match an issue status,
without explicitly marking it session-only.

### 4.4 Layer 3: coherence validator

New validator check: session↔issue status consistency.

| Session status | Allowed issue statuses | Violation |
|---|---|---|
| `planning` | `backlog`, `todo` | warn on later |
| `in_progress` | `todo`, `in_progress`, `in_review` | warn on `done` |
| `in_review` | `in_review`, `done` | **error** on `in_progress` or earlier |
| `done` | `done` | **error** on anything else |

Codes:
- `coherence/issue_status_lags_session` (warning — real slippage happens)
- `coherence/issue_status_ahead_of_session` (error — genuine bug)

This is the check that turns vocabulary alignment from cosmetic to
load-bearing. Runs as part of every `tripwire validate`.

---

## 5. Per-issue artifacts (v0.7b Phase 2)

### 5.1 Manifest

New file: `src/tripwire/templates/issue_artifacts/manifest.yaml`:

```yaml
artifacts:
  - name: developer
    file: developer.md
    template: developer.md.j2
    produced_by: execution-agent
    owned_by: execution-agent
    required: true
    required_at_status: in_review

  - name: verified
    file: verified.md
    template: verified.md.j2
    produced_by: verification-agent
    owned_by: verification-agent
    required: true
    required_at_status: done
```

No `grandfather_before` field. Clean cut per §2.

### 5.2 Schema

Sibling class to `ArtifactEntry` (don't mix session-phase and
issue-status semantics on one model):

```python
class IssueArtifactEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    file: str
    template: str
    produced_by: AgentType
    owned_by: AgentType | None = None
    required: bool = True
    required_at_status: IssueStatus = "done"

    @model_validator(mode="after")
    def _default_owned_by_to_produced_by(self) -> IssueArtifactEntry:
        if self.owned_by is None:
            object.__setattr__(self, "owned_by", self.produced_by)
        return self


class IssueArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifacts: list[IssueArtifactEntry] = Field(default_factory=list)
```

### 5.3 Validator

New check: `check_issue_artifact_presence`. For each issue, for each
required artifact, if `issue.status ≥ required_at_status` and the
file doesn't exist, emit `issue_artifact/missing` (error).

Status ordering helper: `backlog < todo < in_progress < in_review < done`.

Status-transition guards:
- `in_progress → in_review` blocked without `developer.md`
- `in_review → done` blocked without `verified.md`

### 5.4 CLI

New command group `tripwire issue artifact`:

```bash
tripwire issue artifact init <issue-key> <artifact-name> [--force] [--produced-by AGENT]
tripwire issue artifact list <issue-key> [--format text|json]
tripwire issue artifact verify <issue-key>
```

`init` renders the template into `issues/<key>/<file>`. Refuses to
overwrite without `--force`. `--produced-by` override exists for the
PM-as-verifier path until a real verifier ships.

### 5.5 Templates

Two new Jinja templates in `src/tripwire/templates/issue_artifacts/`:

**`developer.md.j2`** — sections: What I built, Key decisions, Files
touched, Tests added, Stop-and-ask points triggered, Followups.

**`verified.md.j2`** — sections: Verified by, Verified at, Verdict
(approved | approved-with-followups | rejected), Acceptance criteria
(checkboxes with evidence), Deviations found, Follow-up issues created.

### 5.6 Issue template update

`default.yaml.j2` DoD checklist points at the CLI instead of literal
paths:

```markdown
## Definition of Done
- [ ] Implementation complete
- [ ] Tests added/updated
- [ ] Completion comment added
- [ ] developer.md ({{ id }}) — see `tripwire issue artifact list {{ id }}`
- [ ] verified.md ({{ id }}) — see `tripwire issue artifact list {{ id }}`
- [ ] Concept nodes created/updated for new artifacts
```

### 5.7 Migration — backfill existing issues

Every issue in every test project at status `in_review` or `done`
gets `developer.md` backfilled. Every issue at `done` gets `verified.md`
backfilled.

**Backfill content:** stub with a honest placeholder, not retroactive
reviews. Template:

```markdown
# Developer notes — <KEY>

## Backfill notice

This artifact was created retroactively during the v0.7 migration.
The issue was closed before per-issue artifacts were enforced.
See PR <number> for implementation details.
```

Same pattern for `verified.md`. Attribution: `pm-agent`.

### 5.8 Reopen behavior

If an issue transitions `done → in_progress`, existing `developer.md`
and `verified.md` persist. The next pass appends `## Re-engagement
YYYY-MM-DD` sections rather than overwriting.

---

## 6. Spawn refinements (v0.7b Phase 3)

### 6.1 Corrected spawn invocation

Amends v0.6c spawn. The `claude -p` invocation becomes:

```bash
nohup claude -p "$(cat <plan-path>)

You are the <agent> agent for session <session-id>.
Execute the plan. Stop at stop-and-ask points.
Open a PR titled '<type>(<session-slug>): <summary>' when done." \
  --name "<session-id>" \
  --effort max \
  --model opus \
  --fallback-model sonnet \
  --permission-mode bypassPermissions \
  --disallowedTools "Agent" \
  --max-turns 200 \
  --max-budget-usd 50 \
  --output-format stream-json \
  --append-system-prompt "tripwire session: <session-id>; project: <project-slug>
If context is getting heavy, use /compact to free space.
Do not use the Agent tool — you are a single-agent session.
Do not use /batch — the work is already decomposed in your plan." \
  > <log-path> 2>&1 &
```

### 6.2 Flag rationale

| Flag | Purpose |
|---|---|
| `--name <session-id>` | Align Claude session name with tripwire session. Enables resume-by-name. |
| `--effort max` | Autonomous agents should use strongest reasoning available. |
| `--model opus` | Complex implementation work; per-session override available. |
| `--fallback-model sonnet` | Resilience against overload. |
| `--permission-mode bypassPermissions` | Autonomous agents can't answer permission prompts. |
| `--disallowedTools "Agent"` | Single-agent constraint — no subagent spawning. |
| `--max-turns 200` | Safety cap. |
| `--max-budget-usd 50` | Hard cost ceiling. |
| `--output-format stream-json` | Real-time event stream (enables monitor). |
| `--append-system-prompt` | Session + project context + self-care instructions. |

### 6.3 `spawn_config` schema

`session.yaml` gains an optional `spawn_config` block:

```yaml
spawn_config:
  model: opus                   # default: opus, override per session
  fallback_model: sonnet        # default: sonnet, override
  effort: max                   # default: max, override
  max_turns: 200                # default: 200, override
  max_budget_usd: 50            # default: 50, override
  permission_mode: bypassPermissions  # default, NOT overridable in v0.7
  disallowed_tools: ["Agent"]   # default, NOT overridable in v0.7
  exclude_dynamic_system_prompt_sections: true  # default, NOT overridable
```

Precedence: CLI flag > session `spawn_config` > `project.yaml.spawn_defaults`
> hardcoded default.

### 6.4 Resume by name

Replaces v0.6c PID-based resume. `tripwire session spawn <id> --resume`:

```bash
claude -p "Continue where you left off." \
  --resume "<session-id>" \
  --effort max \
  --output-format stream-json \
  >> <log-path> 2>&1 &
```

Survives machine reboots; doesn't depend on parent process. The
`--fork-session` flag is used when re-engaging after a failed attempt
to create a clean engagement record while preserving conversation history.

### 6.5 Single-agent constraint (formerly Feature E)

The constraint: one agent per session, always.

**Why:** Testing shows execution-quality degradation when agents spawn
subagents (context loss, weaker synthesis, cost multiplication, invisible
to monitor).

**Enforcement:** `--disallowedTools "Agent"` in every spawn invocation.
Agents can still use direct tools (Bash, Read, Edit, Write, Glob, Grep);
they just can't delegate via the Agent tool or `/batch`.

**What `/batch` is for (not tripwire sessions):** ad-hoc work with no
pre-scoped plan. Tripwire sessions are pre-decomposed by the PM; letting
the agent re-decompose ignores that work and produces worse results.

---

## 7. Session monitor (v0.7b Phase 4)

### 7.1 Interface

**Slash command:**
```
/pm-session-monitor [session-id ...] [auto-remediate stuck|ci-failure|...]
```

- No args: monitor all `in_progress` sessions.
- With session ids: monitor only those.
- Natural-language auto-remediate args (parsed in slash command body)
  elevate behavior from read-only default to targeted auto-actions.

**CLI:**
```
tripwire session monitor [session-id ...] [--format text|json]
```

One-shot snapshot. The slash command wraps this in a `/loop` dynamic-mode
self-paced loop.

### 7.2 Data sources

**Primary: stream-json log tailing.** Reads the log written by the
refined spawn (§6) via `tail -f`. Each line is a JSON event:

```json
{"type":"assistant","message":{"content":"..."},"turn":1}
{"type":"tool_use","tool":"Edit","input":{"file_path":"..."},"turn":2}
{"type":"tool_result","output":"...","turn":2}
{"type":"usage","total_tokens":15234,"cost_usd":0.42,"turn":2}
```

**Fallback: git + GitHub polling.** When the log isn't available:

| Signal | Source |
|---|---|
| New commits | `git -C <wt> log --oneline -5` |
| PR opened | `gh pr list --head <branch>` |
| CI status | `gh pr checks <pr-number>` |
| Agent process alive | `kill -0 <pid>` |
| PR review comments | `gh pr view <number> --comments` |

### 7.3 Auto-actions (read-only default)

Default behavior is read-only automation — no mutating actions without
explicit opt-in via slash command args.

| Event | Default action | Opt-in auto-remediation |
|---|---|---|
| Agent committed progress | Log progress in monitor output | — |
| PR opened | Auto-run `/pm-session-review` (§8) | — |
| CI failed | Alert; summarize failure | `/pm-session-monitor auto-remediate ci-failure` → attach `/autofix-pr` |
| Agent process died | Alert; mark session `failed` | `/pm-session-monitor auto-remediate stuck` → re-engage with `--resume` |
| Agent stuck (no events N min) | Alert | Same opt-in |
| Cost threshold approaching | Alert | — |
| All sessions completed | Alert; suggest next launches | — |

Action scope is controlled per-invocation via natural-language args in
the slash command body. No separate flag-taxonomy.

### 7.4 Self-pacing

`/loop` dynamic mode. Cadence adapts:
- Active commits flowing: 60–90s between ticks
- Waiting for CI: 120–270s
- Idle (no commits 10+ min): 600–1200s
- Event detected: immediate tick, then resume cadence

### 7.5 Monitor commits progress

Every tick, monitor commits a status snapshot to the project repo
(batched per tick, not per event). One commit message summarizes all
detected events. This creates an audit trail in the project history.

### 7.6 Human stepping in

Commits to a session branch by the human are attributed to the session
in the monitor's output. Monitor doesn't distinguish "agent committed"
from "human committed on behalf of agent" — both count as session
progress.

---

## 8. Session review (v0.7b Phase 5)

### 8.1 Interface

**Slash command:**
```
/pm-session-review <session-id> [--pr <number>]
```

**CLI:**
```
tripwire session review <session-id> [--pr <number>] [--format text|json]
```

Local execution only (PM session). No GitHub Action counterpart in v0.7.

### 8.2 What it checks

**Per-issue acceptance criteria verification:**
For each issue in `session.yaml.issues[]`:
1. Read `issues/<key>/issue.yaml` — extract acceptance criteria
2. Read the PR diff — map changed files to the issue's Repo scope
3. For each criterion: evidence in the diff that it's met?
4. Flag unverified criteria

**Deviation detection:**
1. Files touched vs issue Repo scope — flag unspec'd files
2. Dependencies added vs what issues call for — flag extras
3. Directory layout vs Repo scope paths — flag divergence

**Plan adherence:**
1. For each plan.md step: matching files/changes in the diff?
2. Flag steps with no evidence

**Stop-and-ask audit:**
1. Read Execution constraints for "stop and ask" clauses
2. Check if triggered conditions are visible without the agent having stopped

### 8.3 Output channels

1. **PM session output** — structured summary (text or JSON).
2. **PR comments** — primary PM ↔ PR channel. The review posts a summary
   comment on the PR with findings. Per-finding inline comments at the
   specific file:line.
3. **`verified.md` side-effect** — for each issue covered by the session:
   - If `issues/<key>/verified.md` doesn't exist: write it from the review
     output, attribution `pm-agent`.
   - If exists and attributed to a non-PM agent (future verifier agent):
     read-only, skip write, factor existing content into the summary.
   - If exists and attributed to `pm-agent`: append a `## Re-review <date>`
     section (preserves history).

### 8.4 Blocking on errors

Exit codes:
- `0` — approved, no blocking issues
- `1` — approved with notes (deviations but acceptance criteria met)
- `2` — unverified acceptance criteria or plan divergence (blocking)

A `/pm-session-complete` run refuses to transition a session to
`completed` if the most recent review returned exit 2 (unless
`--force-review` is passed).

The review itself does NOT block the PR merge via GitHub Actions in
v0.7 — it's local PM tooling. The merge-block comes via the PM
refusing to call `/pm-session-complete` until errors are resolved.

---

## 9. Session complete (v0.7b Phase 6)

### 9.1 Interface

**CLI:**
```
tripwire session complete <session-id> [--skip-artifact-check]
                                         [--skip-worktree-cleanup]
                                         [--force]
                                         [--force-review]
                                         [--dry-run]
```

**Slash command:**
```
/pm-session-complete <session-id> [closing-note]
```

### 9.2 CLI behavior

1. Verify status is `in_progress` or `in_review` (refuse otherwise;
   `--force` overrides).
2. Verify PR merged. Refuse with `complete/pr_not_merged` unless
   `--force`.
3. Verify per-issue artifacts present for every issue in session
   (developer.md at `in_review`, verified.md at `done`). Refuse if
   missing (Phase 2 enforcement; no override).
4. Verify most recent session review didn't return exit 2. Refuse
   unless `--force-review`.
5. Compute concept-node reconciliation diffs (see §9.3).
6. Transition `session.yaml.status` → `done`.
7. Update `engagements[]` with `ended_at` and `outcome`.
8. Worktree cleanup (unless `--skip-worktree-cleanup`).
9. Print: issues to close, sessions unblocked, worktrees removed.

### 9.3 Slash command behavior

Wraps CLI. The slash command body instructs the PM agent to:

1. Run `tripwire session complete <id> --skip-worktree-cleanup --dry-run`
   to preview.
2. If PR not already reviewed: run `/pm-session-review <id>`. Handle
   errors before proceeding.
3. **Node reconciliation** (PM-reviewed, not auto-applied):
   - CLI computes proposed diffs for each node referenced by the
     issues in the session, comparing node descriptions against the PR
     diff.
   - PM agent reads each diff, decides whether to apply (possibly
     editing the proposed text).
   - Approved diffs are written.
   - `tripwire refs reverse <node-id>` logs downstream sessions
     affected by each updated node.
4. Close each issue → `done` with completion comment.
5. Run `tripwire validate --strict` (catches coherence violations
   from §4.4 Layer 3).
6. Remove worktrees.
7. Commit: `complete: <session-id> (ISSUE-KEYS...)`.
8. Report: issues closed, nodes updated (with downstream impact),
   sessions unblocked, recommended next launches.

### 9.4 Error cases

| Code | Trigger | Fix hint |
|---|---|---|
| `complete/not_active` | wrong status | Check session status |
| `complete/missing_artifacts` | per-issue artifacts absent | Run `tripwire issue artifact init` |
| `complete/issue_not_closeable` | issue can't transition to done | Check status_transitions |
| `complete/worktree_dirty` | uncommitted changes | Commit/stash or `--skip-worktree-cleanup` |
| `complete/pr_not_merged` | PR exists but unmerged | Merge first or `--force` |
| `complete/review_blocking` | last review returned exit 2 | Fix review findings or `--force-review` |
| `complete/node_recon_unapproved` | PM didn't approve all proposed node diffs | Apply or dismiss each |

---

## 10. CI + PyPI + project templates (v0.7b Phases 7–8)

### 10.1 Tripwire-tool CI

New file: `tripwire/.github/workflows/ci.yml`. Runs on every PR to
tripwire and every push to `main`.

Steps (minimal, single Python version):
- checkout
- install uv
- `uv sync`
- `uv run ruff check`
- `uv run ruff format --check`
- `uv run pytest tests/ -q`

Python: 3.13. OS: ubuntu-latest. Target: under 3 minutes per run.

Matrix across Python versions and OSes is explicitly out of scope
(YAGNI until we have a reason).

### 10.2 PyPI publishing

New file: `tripwire/.github/workflows/publish.yml`. Triggers on
`push` of tags matching `v*`.

Steps:
- checkout
- install uv
- `uv build`
- `uv publish --token $PYPI_API_TOKEN`

Secret: `PYPI_API_TOKEN` added to repo secrets (Seido account).

Version source of truth: `pyproject.toml` `[project].version`. Tag
push means the release workflow trusts the tag matches pyproject —
we bump pyproject first, then tag.

**Release process:**
1. PR that bumps `pyproject.toml` version and updates changelog
2. Merge PR
3. `git tag v0.7.0` and `git push --tags`
4. Publish workflow runs, uploads to PyPI

First published version is `v0.7.0` under the `tripwire` name.

### 10.3 Project CI workflow template

New template: `src/tripwire/templates/project/.github/workflows/tripwire.yml.j2`.
Jinja-rendered by `tripwire init` into `.github/workflows/tripwire.yml`
in every new project.

Workflow content:

```yaml
name: Tripwire checks
on:
  pull_request:
  push:
    branches: [main, master]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Install tripwire
        run: uv tool install tripwire=={% raw %}{{ tripwire_version }}{% endraw %}
      - name: Validate
        run: tripwire validate --strict --format=json
      - name: Lint scoping
        run: tripwire lint scoping
      - name: Lint handoff
        run: tripwire lint handoff
      - name: Lint session
        run: tripwire lint session
      - name: Brief (smoke test)
        run: tripwire brief --format=json > /dev/null
```

Renders with `tripwire_version` from `project.yaml`.

### 10.4 `tripwire ci install` command

For existing projects to adopt CI without re-running `tripwire init`.

```
tripwire ci install [--force] [--project-dir PATH]
```

- Reads `project.yaml.tripwire_version`.
- Renders the template into `.github/workflows/tripwire.yml`.
- Refuses if the file exists unless `--force`.

### 10.5 `tripwire init` — CI by default

`tripwire init` creates `.github/workflows/tripwire.yml` by default.
Opt out via `--skip-ci`.

Adds `.github` to the `CREATED_DIRS` constant for coverage in init
tests.

### 10.6 Version pinning philosophy

Projects pin to an exact tripwire version. Bumping is a deliberate PR:

1. Edit `project.yaml.tripwire_version` to new version.
2. Run `tripwire ci install --force` to re-render the workflow with
   the new version.
3. Commit both changes as one PR.
4. CI on that PR runs the new tripwire version against the project.

This ensures version bumps are visible, reviewable, and atomic.

---

## 11. Cross-feature integration

### 11.1 Monitor → Review

When monitor (§7) detects a PR opened on a session's branch, it
auto-runs `/pm-session-review` (§8) with read-only auto-actions default
(Q7=B). Review posts findings as PR comments. If exit 2, monitor flags
as blocking in its output.

### 11.2 Review → verified.md

`/pm-session-review` writes `verified.md` per §8.3 — single path for
producing the artifact in v0.7. Flexible handling when artifact already
exists (future verifier agent path).

### 11.3 Complete → Review + Artifacts + Node recon

`/pm-session-complete` (§9.3) orchestrates:
1. `/pm-session-review` if not already run (writes verified.md)
2. Per-issue artifact presence check (§5.3) — enforces both developer.md
   and verified.md
3. Node reconciliation (PM-reviewed, Q10=B)
4. Issue close loop
5. Coherence validator (§4.4) catches any session↔issue drift

### 11.4 Spawn → Monitor

`--output-format stream-json` (§6.1) enables monitor's primary data
source (§7.2). `--name <session-id>` enables resume-by-name.
`--max-budget-usd` surfaces cost events monitor threshold-checks.

### 11.5 CI → Per-issue artifacts + Coherence

Project CI (§10.3) runs `tripwire validate --strict` which includes:
- `check_issue_artifact_presence` (§5.3) — missing developer/verified
  blocks merge
- Coherence validator (§4.4) — session↔issue mismatch blocks merge

CI is where Phase 2 and Phase 1 enforcement actually bites.

### 11.6 Vocabulary → everywhere

Phase 1 (§4) lands first. All subsequent phases reference the new
vocabulary. No mid-phase flip.

---

## 12. Migration & backcompat

Clean cut everywhere. No grandfather clauses, no legacy aliases.

### 12.1 Migration PR checklist

Landed as part of v0.7a rename and v0.7b Phase 1:

- All `keel` references → `tripwire`
- All `ArtifactPhase` YAML values remapped (`implementing` →
  `in_progress`, `verifying` → `in_review`, `completion` → `done`)
- All session YAMLs across 3 test projects updated
- All skill docs, reference docs, spec docs updated
- `project.yaml.keel_version` field → `tripwire_version` in 3 test
  projects
- `.keel/` → `.tripwire/` hidden dirs (if any exist)
- `.keel.lock` → `.tripwire.lock`
- Per-issue artifact backfill (developer.md, verified.md) with
  placeholder stubs (§5.7)

### 12.2 Existing PRs on keel

PRs #5 and #6 (frontend-markdown, backend-server-scaffold) are
currently open. Strategy:
- Land v0.7a rename first on main
- Those PRs rebase onto the renamed main and adjust imports/config
  names
- They're small PRs; the rebase is mechanical

---

## 13. Release sequencing

### 13.1 v0.7a (rename)

Single branch, single merge. Estimated 1-2 hours of agent work.

Steps:
1. Update `pyproject.toml` name, scripts
2. Rename `src/keel` → `src/tripwire`
3. Rename GitHub repo (done in UI; redirects preserved)
4. Update every import path (src + tests)
5. Update every reference in templates, skill docs, spec docs
6. Rename config fields in models + migration for existing project
   YAMLs
7. Update three test projects' `project.yaml`
8. Full test suite clean, full lint clean
9. PR, review, merge
10. Tag `v0.7a` (pre-release)

### 13.2 v0.7b (features)

Single branch (`feature/v0.7b`), 8 phases, each mergeable
independently:

| Phase | Feature | Approx effort |
|---|---|---|
| 1 | Vocabulary alignment (§4) | 3.5 days spec / ~1 hr agent |
| 2 | Per-issue artifacts (§5) | 7.5 days spec / ~2 hr agent |
| 3 | Spawn refinements (§6) | 2.5 days spec / ~45 min agent |
| 4 | Session monitor (§7) | 7 days spec / ~2 hr agent |
| 5 | Session review (§8) | 7 days spec / ~2 hr agent |
| 6 | Session complete (§9) | 4 days spec / ~1 hr agent |
| 7 | Tripwire-tool CI (§10.1) | 0.5 days / ~15 min |
| 8 | PyPI + project templates (§10.2-5) | 3 days / ~1 hr |

Spec total: ~35 days. With AI agents: measured in hours.

Release ordering: Phase 1 first (prerequisite), then all others in
parallel where possible. Suggested order above.

---

## 14. Error code summary

New error codes introduced by v0.7:

| Code | Feature | Severity |
|---|---|---|
| `coherence/issue_status_lags_session` | §4 | warning |
| `coherence/issue_status_ahead_of_session` | §4 | error |
| `issue_artifact/missing` | §5 | error |
| `issue_artifact/wrong_status` | §5 | error (transition guard) |
| `complete/not_active` | §9 | error |
| `complete/missing_artifacts` | §9 | error |
| `complete/issue_not_closeable` | §9 | error |
| `complete/worktree_dirty` | §9 | error |
| `complete/pr_not_merged` | §9 | error |
| `complete/review_blocking` | §9 | error |
| `complete/node_recon_unapproved` | §9 | error |
| `monitor/log_missing` | §7 | warning (falls back to polling) |
| `monitor/session_not_executing` | §7 | error |
| `review/unverified_criteria` | §8 | error (exit 2) |
| `review/plan_deviation` | §8 | error (exit 2) |
| `review/unspec_files` | §8 | warning |
| `ci/workflow_exists` | §10 | error (without `--force`) |

---

## 15. Testing

See draft specs for detailed test matrices. Consolidated counts:

| Feature | New tests |
|---|---|
| Vocabulary alignment | ~10 |
| Per-issue artifacts | ~15 |
| Spawn refinements | ~8 |
| Session monitor | ~12 |
| Session review | ~10 |
| Session complete | ~10 |
| CI + PyPI + templates | ~6 |
| Rename (v0.7a) | smoke tests + full suite continues passing |

All tests pass on every PR via tripwire-tool CI (§10.1).

---

## 16. Open items to resolve at implementation time

- PyPI `tripwire` availability check — if taken, fallback to
  `tripwire-pm`. Decision made when Phase 7 starts.
- `--exclude-dynamic-system-prompt-sections` — audit against current
  `claude --help` version before including in spawn invocation. If
  not present, drop from the spec.
- `project.yaml.spawn_defaults` field — scoped as a schema addition
  but fine detail (which keys) deferred to Phase 3 implementation.
- Stream-json event types that the monitor ignores vs hard-parses —
  fine detail for Phase 4.

---

## 17. Cross-references

- `2026-04-16-v07-pm-monitor.md` — superseded by this document
- `2026-04-17-v07-issue-developer-notes.md` — superseded by this document
- `2026-04-16-session-spawn-agenda-worktrees-design.md` — v0.6c
  (previous release); §6 amends the spawn invocation
- `docs/tripwire-containers.md` — container runtime (post-v0.7)
- Claude Code CLI reference (v2.1.110+) — flag inventory
