# Tripwire v0.7.5 — draft PRs at session-start (candidate)

**Status**: candidate spec (not queued for v0.7.4; picked up after v0.7.4 lands)
**Date**: 2026-04-24
**Depends on**: v0.7.4 per-session project-tracking worktrees (this spec co-designs with them)
**Sibling specs**:
- `2026-04-24-v074-handoff.md` — must land first
- `2026-04-24-v08-bidirectional-concept-graph.md` — orthogonal

---

## 1. Context

Today `tripwire session spawn` creates the worktree + starts the agent but
does no remote git action until `tripwire session complete` pushes the
branch and opens a PR. The agent is invisible to anyone not tailing the
stream-json log, and mid-session crashes leave the work in an on-disk
worktree with no record anywhere else.

Opening a **draft PR at session-start** — immediately after worktree
creation, against the branch we just cut — unlocks five wins:

1. **Visibility from minute one.** A draft PR gives a stable URL with a
   live diff. Richer signal than the stream-json log: browse in-flight
   code in GitHub's UI, comment on lines, see what's touched and what
   isn't.
2. **Continuous CI feedback.** Every push during the session triggers
   tests/lint. Breakage surfaces at commit time, not at the final-verify
   pass right before exit. Catches "build clean, tests broken" early.
3. **Crash recovery.** If the process dies mid-session (network, OOM,
   runtime bug), the PR still exists with whatever commits already
   landed.
4. **Pairs cleanly with v0.7.4 project-tracking worktrees.** The dual-PR
   flow at `complete` flips both draft PRs to **ready** instead of
   creating them. Same GH operation count, rearranged timing — plus a
   second draft PR on the project-tracking repo for session artifacts.
5. **Reinforces commit-early discipline.** Today agents tend to land one
   massive end-of-session commit (observed: frontend-views-core's
   session-close PR + self-review all in one). A live draft PR nudges
   toward smaller themed commits because there's already something to
   push to.

---

## 2. Implementation sketch

**The wrinkle.** `gh pr create` refuses if there are zero commits
between the feature branch and base. Worktree creation + checkout is not
a commit.

**Options:**

- **(a) Empty marker commit at prep time.** After `worktree_add`,
  `git commit --allow-empty -m "session(<id>): start"` in the worktree,
  then push + `gh pr create --draft`. Squash-merge at `complete`
  erases it from history. One line of code in `prep.py`, low
  brittleness.
- **(b) Deferred-creation on first real commit.** Hook or wrapper on
  the agent's first `git commit` that also pushes + opens the draft
  PR. More involved; relies on hook plumbing; less predictable
  timing.

**Recommendation: (a).** The empty commit vanishes under squash-merge
and the code is trivial. The small cost — an empty commit visible in the
worktree's `git log` until squash — is the price for predictable
behaviour.

**Code changes (expected scope; fill in during planning):**

- `src/tripwire/runtimes/prep.py` — after each `worktree_add`, emit the
  empty session-start commit, push, `gh pr create --draft`. Store the
  PR URL on the `WorktreeEntry` (new field `draft_pr_url: str | None`).
- `src/tripwire/core/session_complete.py::_flip_drafts_to_ready` (new) —
  replace the "create PR" step with a "flip to ready" step:
  `gh pr ready <number>` per worktree. Fall back to "create PR" for
  worktrees where `draft_pr_url` is unset (belt-and-braces for sessions
  started before v0.7.5).
- `src/tripwire/cli/session.py::session_abandon_cmd` — close the draft
  PR(s) so they don't pile up as orphan drafts.
- Template / log surface — print the draft PR URL(s) to the operator
  on successful spawn so they're one click from the live view.

**Paired behaviour with v0.7.4.** When v0.7.4 is live, each session has
**two** worktrees — code repo + project-tracking. v0.7.5 opens **two**
draft PRs at spawn and flips both to ready at complete. Same loop, just
iterated.

---

## 3. Risks / costs

- **PR list noise.** N in-flight sessions = N draft PRs. Mitigated by
  GitHub's draft filter and the fact draft PRs don't trigger reviewer
  notifications by default.
- **Wasted CI minutes.** Early reconnaissance commits that wouldn't
  otherwise trigger CI now do. Marginal if CI is per-minute billed.
  Acceptable given the CI-feedback win (benefit 2).
- **Orphan draft PRs from abandoned sessions.** `tripwire session
  abandon` must also close the PR. In scope — listed above.
- **First-spawn UX if `gh` not installed / not authed.** Today `gh` is
  only exercised at `complete`. Spawning would fail sooner. Good — the
  fast-fail is preferable to "agent ran for 8 minutes, then complete
  failed on a missing tool".

---

## 4. Out of scope (deferred)

- **Draft PR title / body templates.** v0.7.5 ships with a minimal
  placeholder; the session-complete flow already rewrites the final
  title + body. No need to design a mid-session body format.
- **Reviewer auto-assignment.** Draft PRs stay reviewer-unassigned;
  flip-to-ready can assign.
- **Auto-transition `executing` → `in_review` on draft-PR-ready.**
  Belongs to the v0.8 agent-messaging thread, not here.
- **Draft PRs for manual-runtime sessions.** Manual runtime is a
  prep-only path; skip unless the operator explicitly opts in.

---

## 5. Why this is a v0.7.5 candidate, not v0.7.4

v0.7.4 is closing correctness gaps (parallel-session write races,
false-positive plan warnings, stale UI copy). This spec is a
quality-of-life improvement: the visibility / CI / crash-recovery wins
are large, but no current workflow is *broken* without it. Shipping
alongside v0.7.4 would widen the blast radius of that release. Shipping
right after, with v0.7.4's per-session project-tracking worktree as the
foundation, gives a clean v0.7.5 focused on one thing: continuous
session visibility from minute one.

---

## 6. Open questions

- **Squash vs merge default.** The empty session-start commit relies on
  squash-merge to disappear. If a project enforces merge-commit, the
  commit stays in history. Tolerable? Probably yes — one noisy commit
  per session is cheap — but worth calling out.
- **Draft PR base branch.** Today `base_branch` is per-repo-binding.
  Project-tracking repo's base may or may not be `main`; needs the
  same resolution path.
- **How to name the PR title mid-flight.** Candidate: `[draft] session
  <id>` with body `tracking {session_id}; updated by agent in-flight`.
  Revisit during implementation planning.
