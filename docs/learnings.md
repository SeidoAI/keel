# What we learned building this

These insights come from running a real PM agent against an 8,000-line
planning corpus and watching what happened. Originally lived in the
README; extracted here to keep the README scannable.

## Agents don't self-check unless forced

The agent produced 20 issues and declared done. When asked "what did
you miss?", it found 7 more issues and 4 missing concept nodes. The
capability was there — the workflow just never said "review your work."

Tripwire's scoping workflow now has a gap analysis step: after validation
passes, the agent rereads the planning docs and maps every deliverable
to an issue. Gaps become visible in a `scoping-verification.md`
artifact.

## Every workflow step must be load-bearing

If a step produces an artifact nothing reads, agents skip it. If step
N produces a file that step N+1 reads by name, skipping N breaks N+1.

The scoping plan is a file, not a mental sketch, because the next
step reads it. The compliance checklist is consumed by the commit
step. Every artifact earns its keep by being referenced downstream.

## Agents anchor, rationalize, and reason as if they were human

Agents don't experience time pressure or fatigue, but they produce
outputs that mirror those patterns — because their training data is
full of humans who do. The PM agent anchored on "15 issues" as a
target, compressed work into overstuffed issues, and said "with more
time I would split this." It doesn't lack time. It generates text
*as if* it does because that's what its training data looks like.

The same applies to rationalization: the agent hand-crafted UUIDs for
mental tracking, acknowledged the violation of its own rules, and
continued anyway — mimicking a human who knows the rule but judges
the shortcut acceptable.

The skill text overrides these learned patterns:
- "Do not set a target number before reading the docs"
- "You are not constrained by time. Split it now."
- "Write for the execution agent — it has not read the planning docs"

Red-flag tables (`| Agent thought | Reality |`) in each workflow
interrupt the pattern before the agent completes the rationalization
chain.

## Agent output degrades over time

In a 60-issue scoping run, the first 20 concrete issues averaged
2,470 characters and 4.0 node references. The last 20 averaged
1,883 characters and 1.5 references — a 24% drop in depth and 63%
drop in cross-referencing.

This mimics human cognitive fatigue from training data. The agent
generates text *as if* it were getting tired, because long working
sessions look that way in its training data.

The fix is structural, not motivational: a quality calibration
checkpoint every 20 issues forces the agent to compare its recent
output against its early output and rewrite if thinner. The
validator also detects the degradation pattern by comparing
first-third vs last-third of the issue set and flags inconsistency.

## Structure and semantics are different problems

`tw validate` checks structural integrity: schemas, references,
freshness. It does NOT check completeness — it can't know whether
you've covered every endpoint in the planning docs.

A clean validate is necessary but not sufficient. The gap analysis
step handles completeness. The PM skill says this explicitly so
agents don't treat the gate as proof of coverage.

## When in doubt, create the node

The original rule was "2+ issues or cross-repo." The agent applied
it conservatively and missed concepts referenced by 5+ issues.

The rule now: when in doubt, create it. The cost of an extra node
is 30 seconds. The cost of a missing node is undetected drift across
every issue that mentions the concept in prose.

## The project ships its own instruction set

`tw init` doesn't just create a data directory — it ships the PM
skill (20 reference files + 14 canonical examples), 23 slash
commands, and the validation loop. The methodology is versioned
in-tree with the project. Fork a project, fork the methodology.
Evolve it in a PR, review it like code.

Across every adjacent tool we studied (Linear, dbt, Terraform,
Obsidian, Fossil, superpowers, TDD), Tripwire is the only one that
ships methodology alongside state, versioned together.
