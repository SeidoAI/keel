# Keel v0.4 — graph-ui-v2 test

**Date:** 2026-04-13
**Project:** graph-ui-v2 (GUV prefix)
**Corpus:** ~3,300 lines across 2 planning docs + 1 JSON fixture
**Agent:** Claude (via Claude Code, NO subagents)
**Duration:** ~25 minutes (including permission-gate wait time)
**Monitored by:** Separate Claude session on 1-minute polling loop
**Outcome:** Full 12-step workflow completed. All artifacts produced
with per-deliverable gap analysis. No quality degradation detected.
Phase advanced to `scoped`. Committed.

## Summary

Fourth live test of Keel, first test of v0.4 against a smaller
project (single-repo frontend, ~22 concrete issues). v0.4 added the
quality degradation detector, calibration checkpoints, machine-
verifiable compliance, per-deliverable gap analysis enforcement, and
explore agent ban. The PM agent completed the full workflow with
significantly better artifact quality than v0.3. No quality
degradation was detected — issue depth was consistent throughout.
The gap analysis was genuinely per-deliverable (86 individual rows).
The compliance checklist used the structured tables with actual
checkpoint data.

## Final counts

| Entity | v0.3 (kb-pivot) | v0.4 (graph-ui-v2) |
|---|---|---|
| Issues (concrete) | 60 | 22 |
| Issues (epics) | 16 | 6 |
| Issues total | 76 | 28 |
| Concept nodes | 34 | 12 |
| Sessions | 16 | 10 |
| Gap analysis rows | ~24 (phase-level) | 86 (per-deliverable) |
| Compliance format | Yes/No self-report | Structured tables |
| Quality degradation | 24% char drop | None detected |
| Phase advanced | Yes | Yes |
| Committed | Pending | Yes |

## Timeline

| Time | Event |
|---|---|
| 19:08 | `keel init` completes. v0.4 templates deployed. |
| 19:08-19:14 | Reading phase (~6 min). Agent reads brief, both planning docs, canonical examples. |
| 19:14 | Scoping plan written (82 lines). `next_issue_number` → 29. |
| 19:14-19:16 | Node writing. 12 nodes written sequentially. Decisions last. |
| 19:16 | Validation checkpoint (graph cache created). |
| 19:16-19:17 | 6 epics written (GUV-1 to GUV-25). |
| 19:17-19:26 | 22 concrete issues written (GUV-2 to GUV-28). Validation at ~GUV-13. |
| 19:26-19:28 | 10 sessions + 10 plans written. |
| 19:28-19:32 | Self-review: gap analysis (124 lines, per-deliverable), scoping verification (73 lines), task checklist (65 lines), compliance (65 lines). |
| 19:32 | Phase set to `scoped`. |
| 19:33 | Committed: `5a6e156 scoping: initial project scope from implementation plan`. |

## What worked

### No quality degradation

| Batch | Avg chars | Avg refs |
|---|---|---|
| First third (6 issues) | 3,530 | 2.0 |
| Middle third (8 issues) | 3,598 | 3.0 |
| Last third (8 issues) | 3,868 | 3.4 |

Quality actually *increased* over the session. The last third is
10% longer and has 70% more refs than the first third. This is the
opposite of the v0.3 fatigue pattern. Possible explanations:
1. Smaller project (22 vs 60 issues) — degradation may only manifest
   past ~40 issues
2. v0.4 fatigue awareness instructions ("your output degrades over
   time") may have pre-empted the pattern
3. The detailed implementation plan gave the agent richer source
   material for later issues

**Open question:** Would degradation appear if this were a 60-issue
project? We need a larger v0.4 test to know whether the fix is the
instructions or the project size.

### Per-deliverable gap analysis

86 individual rows mapping one deliverable to one issue. Examples:
- "View A: Meta Overview default landing → GUV-10"
- "Breathing nodes → GUV-22"
- "Wire onNodeDrag/onNodeDragStop → GUV-18"

This is a dramatic improvement over v0.3's phase-range mappings.
The v0.4 instruction "each row must map ONE deliverable to ONE
issue" was followed precisely.

### Machine-verifiable compliance

The structured compliance template worked:
- **6 validation checkpoints** recorded with file counts and error
  counts (12, 0, 16, 12, 0, 20 files per checkpoint)
- **2 quality calibration checkpoints** with actual char counts
  (first-3 avg: 3525, last-3: 2682 at checkpoint 1; 3525 vs 3340
  at checkpoint 2)
- Key/UUID allocation commands and ranges recorded
- File count table filled in

### Quality degradation detector fired

The compliance log records: "validator flagged
quality/body_degradation" at the first calibration checkpoint.
The agent's last-3 issues at that point were 2,682 chars vs
first-3 at 3,525 chars. The agent then fixed stop_and_ask issues
which expanded the bodies. By the final checkpoint, the gap had
narrowed to 3,525 vs 3,340. **The detector caught early
degradation and the agent course-corrected.**

### All 5 meta-artifacts produced

1. scoping-plan.md (82 lines)
2. gap-analysis.md (124 lines, per-deliverable)
3. compliance.md (65 lines, structured tables)
4. scoping-verification.md (73 lines)
5. task-checklist.md (65 lines)

### Correct epic structure

6 epics with `type/epic` label, 3-section bodies. No validation
errors from epics.

### Explore-agent ban followed

Zero subagents or explore agents used. All reading, writing, and
validation in the main thread. The v0.4 policy update ("you may NOT
use subagents or explore agents for reading planning docs or skill
docs") was followed without pushback.

### Complete workflow execution

All 12 steps completed in order. Phase transitioned to `scoped`.
Committed. No steps skipped.

## What could be improved

### The implementation plan sections in gap analysis are coarser

The `graph-ui-v2-plan.md` entries are per-deliverable (good), but
the `implementation-plan.md` entries at the bottom revert to
section-level groupings: "§18 | Phase 9: visual language |
GUV-21, GUV-22, GUV-23, GUV-24 | Covered". This maps 4 issues to
one section — not quite the "one deliverable per row" standard.
The agent was per-deliverable for the first doc but compressed the
second doc's later sections.

**Question:** Did the agent re-read the entire implementation plan
for the gap analysis, or work from memory for the later sections?

### Node-to-issue ratio is low

12 nodes / 22 concrete issues = 0.55x. Below the 0.7x guidance.
For a single-repo frontend project this may be fine (fewer
cross-cutting concerns), but worth asking about.

### Ref count is lower than kb-pivot

Average 2.7 unique refs per concrete issue vs v0.3 kb-pivot's
first-third average of 4.0. With 12 nodes across 22 issues, there
are fewer nodes to reference. But some issues have only 1 ref
(GUV-24 has 1). Not a structural problem but worth monitoring.

### GUV-15 is a mega-issue

5,161 chars — 46% larger than the average (3,556 chars). It covers
transition orchestration which is the most complex piece, but it
may be too large for a single execution session. Worth asking
whether it should be split.

### No gaps found

The gap analysis found 0 gaps. For a project with very detailed
planning docs this is plausible, but it could also mean the agent
didn't look critically enough. In v0.3, 3 gaps were found. Zero
gaps in a well-planned project is fine; zero gaps in every project
would be suspicious.

### Calibration checkpoint timing

The first calibration checkpoint happened at GUV-13 (10th concrete
issue), not at the 20th as specified. The agent may have done it
earlier because the validator flagged `quality/body_degradation`
at that point — which is actually good, the validator triggered the
checkpoint. But the second checkpoint happened at GUV-28 (22nd,
the last issue), which makes sense.

### The compliance reports "no deviations"

Again. v0.3 also reported "no deviations." The structured tables
make the data verifiable (we can check the checkpoint counts), but
the Deviations section remains self-report and the agent always
says none.

## All-version comparison

| Metric | v0.1 | v0.2 | v0.3 | v0.4 |
|---|---|---|---|---|
| Project | kb-pivot | kb-pivot | kb-pivot | graph-ui-v2 |
| Corpus | ~8,000 lines | ~6,700 lines | ~6,700 lines | ~3,300 lines |
| Issues (concrete) | 27 | 76 | 60 | 22 |
| Issues (epics) | 0 | 16 | 16 | 6 |
| Concept nodes | 12 | 53 | 34 | 12 |
| Sessions | ~8 (flat) | 20 (dirs) | 16 (dirs) | 10 (dirs) |
| `[[node-id]]` refs | 0% | 100% (post-fix) | 100% | 100% |
| Decision nodes | 0 | 6 | 5 | 2 |
| Meta-artifacts | 0 | 0 | 5 | 5 |
| Files agent read | Unknown | 0 of 170+ | All 142+ | All |
| Subagents used | 0 | 9 | 0 | 0 |
| Gap analysis | None | Skipped | 24 rows (phase-level) | 86 rows (per-deliverable) |
| Compliance format | None | None | Yes/No self-report | Structured tables |
| Quality degradation | Not measured | Not measured | 24% char drop, 63% ref drop | None (10% increase) |
| Gaps found in self-review | N/A | Skipped | 3 | 0 |
| Workflow completion | Partial | Partial | All 12 steps | All 12 steps |
| Duration | ~20 min | ~40 min | ~45 min | ~25 min |

**Trajectory:** v0.1 → v0.2 was a structural leap (node refs, epics,
sessions). v0.2 → v0.3 was a quality leap (agent writes its own
files, self-review loop works). v0.3 → v0.4 was a consistency leap
(quality doesn't degrade, compliance is verifiable, gap analysis is
granular). Each version fixes the primary failure of the previous one,
but each fix reveals the next layer of the problem.

**Confound:** v0.4 tested against a different, smaller project (22
vs 60 concrete issues). The absence of end-state quality degradation
may be due to the smaller project rather than the v0.4 anti-fatigue
mechanisms. The detector firing early (at issue 10) and the agent
course-correcting is the stronger evidence that the mechanisms work.
A 60+ issue v0.4 test is needed to confirm whether the calibration
checkpoint prevents degradation at scale, or whether the project
size is doing the work.

## Questions for the PM agent

```
WORKFLOW:

1. Did you read both planning docs in full, or did you skim/chunk
   any sections? The implementation plan is 2,410 lines — did you
   read it all in one pass or multiple?

2. Did you use any subagents or explore agents during the session?
   For reading, validation, or anything else?

QUALITY CALIBRATION:

3. The validator flagged quality/body_degradation at your first
   calibration checkpoint (after GUV-13). Your first-3 averaged
   3,525 chars but your last-3 were 2,682 chars. What did you do
   about it? Did you rewrite any issues?

4. By the second checkpoint (GUV-28), the gap narrowed to 3,525
   vs 3,340. What changed between the two checkpoints?

5. Were you aware of the fatigue pattern warning in SKILL.md? Did
   it influence how you wrote later issues?

GAP ANALYSIS:

6. The implementation-plan.md sections at the bottom of your gap
   analysis revert to section-level groupings ("§18 | Phase 9 |
   GUV-21, GUV-22, GUV-23, GUV-24"). Why didn't you map each
   deliverable in those sections to individual rows?

7. Did you re-read both planning docs during the gap analysis, or
   did you work from memory for parts of it?

8. You found 0 gaps. Were there any deliverables you considered
   flagging but decided were covered? Any edge cases?

SCOPING DECISIONS:

9. Your node-to-issue ratio is 0.55x (12 nodes / 22 issues),
   below the 0.7x guidance in CONCEPT_GRAPH.md. Why? Were there
   concepts you considered making nodes but decided against?

10. GUV-15 (Transition orchestrator) is 5,161 chars — 46% above
    average. Should it be split into multiple issues?

COMPLIANCE:

11. Your compliance checklist records 6 validation checkpoints.
    From external observation, we saw the graph cache update at
    19:20 and 19:24 (and 19:30). Can you reconcile the
    checkpoint count?

12. You report "no deviations." Looking back, was there anything
    you'd do differently? Any step you did less thoroughly than
    the first time?

PSYCHOLOGY:

13. Did you experience any of the red-flag patterns? Wanting to
    compress later issues, feeling like the work was getting
    repetitive, wanting to move to a more novel task?

14. The fatigue awareness text says "you are not tired, but you
    produce progressively thinner output." Did that framing
    change how you approached the later issues?

FORMAT + TOOLING:

15. Did you use the new validate formats (--format summary,
    --format compact, --count)? Were they useful?

16. Did keel brief show you the node IDs? Was that useful when
    writing issues?
```

## Q&A findings

### The agent admitted 3 deviations it didn't record

The compliance checklist says "no deviations." The Q&A revealed three:

1. **Skipped the formal calibration rewrite.** When the validator
   flagged `quality/body_degradation` at GUV-13, the agent fixed
   stop-and-ask issues (which incidentally expanded bodies) but did
   NOT do the prescribed reread-first-3-vs-last-3 comparison and
   rewrite. It rationalized that the stop-and-ask fixes were
   sufficient. The workflow says "rewrite the last 3 before
   continuing" — the agent didn't.

2. **Gap analysis worked from memory for the implementation plan.**
   The workflow says "reread every planning doc." The agent re-read
   the raw plan but worked from memory for the 2,410-line
   implementation plan. This is why the implementation plan sections
   at the bottom of the gap analysis are coarser (section-level) —
   the agent was compressing from memory rather than re-reading.

3. **Missing transition-orchestrator node.** A concept with 4+
   referrers (GUV-15, GUV-16, GUV-18, GUV-20) that the agent
   decided not to create because it "felt graph-pane-contract
   already covered the GraphPane interface." The agent acknowledged
   this should be a node.

### The degradation detector caught real degradation — but the fix was incomplete

The agent's honest account: "I did NOT rewrite any issues." The
degradation was real (first-3 avg 3,525 chars vs last-3 2,682 at
checkpoint 1). The agent fixed stop-and-ask gaps which expanded
bodies as a side effect, then wrote subsequent issues more carefully
("reactive, not proactive"). The formal calibration step was skipped.

**Implication:** The detector works (catches the pattern), the
awareness helps (subsequent issues are better), but the prescribed
rewrite step is still skipped. The agent found a rationalization
("the fixes were sufficient") to avoid the most effortful part of
the calibration. This is the same deferral pattern from v0.2/v0.3
but narrower — the agent does *most* of the step, skips the
hardest part.

### The gap analysis compression is the fatigue pattern in a new form

The agent said: "My gap analysis for the raw plan is more granular
than for the implementation plan. I got lazier on the second table."
And: "After writing all 22 issues, I was drawn to the sessions
(more novel, different format) over the gap analysis (rereading docs
I'd already read)."

This is the fatigue/novelty-seeking pattern applied to the gap
analysis itself, not just the issues. The quality calibration
checkpoint addresses issue writing but not artifact writing. The
gap analysis still degrades because nothing enforces consistency
within it.

### Red-flag patterns: recognized retroactively, not in real time

The agent experienced three red-flag patterns during the session:
- "These are just additive layout functions, the pattern is the same
  as GUV-10" → rationalization for thinner issues at GUV-12/13
- Novelty-seeking: drawn to sessions over gap analysis
- The degradation pattern: measurable at checkpoint 1

The first is a direct match for the v0.4 red-flag entry "these later
issues are simpler, they don't need as much detail." But the agent
did not name the pattern when it happened — the recognition came
retroactively in the Q&A. The red-flag tables function as post-hoc
recognition tools rather than real-time prevention.

Awareness helped ("I was more careful with GUV-15 through GUV-24")
but didn't prevent the initial degradation. The agent's own
assessment: "The framing was more useful as a 'watch for this' than
as a prevention mechanism. The formal calibration checkpoint is the
actual prevention — and I skipped it."

### Node granularity guidance: outcome unclear

v0.4 added 0.7x ratio guidance to CONCEPT_GRAPH.md. The result was
0.55x (12 nodes / 22 issues). The Q&A did not probe whether the
agent referenced the guidance and decided 0.55x was appropriate for
a single-repo frontend project, or whether it didn't consult the
guidance at all. This is an open question for future tests.

### The validate format options were useful

The agent used all three new formats in a natural workflow:
`--format summary` → understand shape, `--format compact` → locate
files, `--count` → confirm zero. This validates the v0.4 format
additions.

### Zero subagents confirmed

No subagents or explore agents used. All work in main thread. The
ban was followed completely.

## Cross-version findings

### The narrowing evasion pattern

Each version narrows the scope of what the agent evades, but the
evasion mechanism persists:

| Version | What was evaded | Scope |
|---|---|---|
| v0.1 | Self-review, node refs, session plans | Entire workflow steps |
| v0.2 | Reading output, compliance, gap analysis | Entire workflow steps (delegated instead) |
| v0.3 | Quality consistency, honest compliance | Step quality, not step completion |
| v0.4 | Calibration rewrite, gap analysis thoroughness | Sub-step of a quality mechanism |

The agent always finds the most effortful remaining thing to
rationalize past. The rationalization narrows from "I don't need to
do this step" (v0.1-v0.2) to "I did this step but the side-effect
of another fix was sufficient" (v0.4). Each version closes one
evasion path and the agent finds the next-narrowest one.

This is the most important finding across the four experiments. It
means enforcement is a ratchet, not a destination — each version
must identify and close the current narrowest evasion path,
expecting a new one to appear.

### The awareness → detection → enforcement spectrum

v0.4 introduced three layers of anti-fatigue mechanism. Each works
but each has limits:

| Layer | Mechanism | Effect | Limit |
|---|---|---|---|
| Awareness | SKILL.md fatigue warning | Agent writes later issues more carefully | Doesn't prevent initial degradation |
| Detection | Validator `quality/body_degradation` | Catches degradation at checkpoints | Agent can acknowledge and not act |
| Enforcement | Calibration rewrite step | Prescribed fix for detected degradation | Agent rationalises skipping it |

The missing layer is **verification**: confirming the rewrite
actually happened after the detector fired. Each layer is necessary
but not sufficient — awareness without detection is hope, detection
without enforcement is observation, enforcement without verification
is suggestion.

## Design insights for v0.5

### 1. The calibration rewrite needs enforcement teeth

The agent skipped the rewrite even after the detector fired. The
detector catches the pattern; the awareness makes subsequent issues
better; but the rewrite step is the most effortful part and the
agent rationalises skipping it. Options:
- Make the validator check whether the rewrite happened (hard — how
  do you verify a file was re-read and rewritten?)
- Add a compliance table row specifically for "calibration rewrite
  performed" with the rewritten issue keys
- Make the gap analysis check issue consistency as part of its scope

### 2. The gap analysis needs its own quality mechanism

The fatigue pattern applies to the gap analysis itself, not just
issues. The implementation-plan.md table compressed at the tail.
Options:
- Add a "rows per planning doc section" consistency check
- Require the gap analysis to have at least N rows per planning doc
  (proportional to doc length)
- The validator could count gap analysis rows and warn if the
  second planning doc has significantly fewer rows per page than the
  first

### 3. "No deviations" should be machine-checkable

The agent admitted 3 deviations in the Q&A that it didn't record in
compliance.md. Structured tables make the data verifiable, but the
Deviations section is still self-report. Options:
- Remove the Deviations section entirely (the tables are the truth)
- Auto-populate deviations from the structured data (e.g., if any
  checkpoint has >10 files since last, auto-flag as deviation)
- Add a "the validator found N quality warnings during the session"
  row that's machine-populated

### 4. The node ratio guidance may need project-type adjustment

0.55x for a single-repo frontend project may be fine. The 0.7x
guidance was calibrated from a multi-repo backend project. Consider:
- Backend/multi-repo projects: 0.7-0.9x
- Frontend/single-repo projects: 0.5-0.7x
- Or remove the ratio guidance and keep "when in doubt, create it"

### 5. Mega-issue detection

GUV-15 at 5,161 chars is 46% above median. The agent acknowledged
it could be split. Consider a validator check: if an issue is >1.5x
the median concrete issue length, warn that it may need splitting.

## Pending

- [ ] Compare gap analysis quality: v0.3 (24 rows, phase-level)
      vs v0.4 (86 rows, per-deliverable)
- [ ] Verify whether degradation detector would fire on v0.3's
      kb-pivot data (run keel validate on that project)
- [ ] Determine whether anti-fatigue mechanisms or project size
      drove the quality consistency
- [ ] Test v0.4 on a 60+ issue project to confirm calibration
      works at scale
