"""lint/concept_drift — flag load-bearing terms that should be concept nodes.

Replaces the old `lint/issue_body_orphan_concepts` heuristic, which ran a
single regex+stopword pass and produced thousands of warnings on a normal
project. This rule combines several weak signals so that a finding only
fires when multiple signals line up — precision-first.

Pipeline:

1. Strip noise zones — markdown headers, fenced code blocks, inline code,
   `[[ref]]` content, URLs, checklist scaffolding. Only "real prose" survives.
2. Extract candidates from the prose:
   - Multi-word Title-Case noun phrases (`WebSocket Hub`).
   - kebab-case identifiers (`project-shell`) — almost certainly someone
     dropping the `[[…]]` brackets.
3. Score each candidate by combining cross-issue frequency, within-issue
   frequency, and kebab-case shape. Weak single-mention multi-word terms
   are dropped.
4. Filter against existing nodes (id / name / fuzzy normalised match) and
   the per-project allowlist.
5. Cap reports at 10 per issue — even after the precision filter, a runaway
   issue body shouldn't drown out other rules.

Tunings (raise to make the rule quieter, lower to widen recall):

- `MIN_CROSS_ISSUE_FREQ = 2` — multi-word phrase must appear in ≥2 issues
  unless within-issue freq carries it.
- `MIN_WITHIN_ISSUE_FREQ = 3` — a single-issue mention is too weak; 3+
  uses in one issue is enough on its own.
- `MAX_FINDINGS_PER_ISSUE = 10`.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from tripwire.core.lint_allowlist import load_concept_allowlist
from tripwire.core.linter import LintFinding, register_rule
from tripwire.core.node_store import list_nodes
from tripwire.core.store import list_issues

# ---------------------------------------------------------------------------
# Tunings (see module docstring).
# ---------------------------------------------------------------------------

MIN_CROSS_ISSUE_FREQ = 2
MIN_WITHIN_ISSUE_FREQ = 3
MAX_FINDINGS_PER_ISSUE = 10

# ---------------------------------------------------------------------------
# Noise-zone stripping. Hand-rolled — we only need section-header /
# code-block / fence detection, not a full markdown AST.
# ---------------------------------------------------------------------------

_FENCE = re.compile(r"^\s*(?:```|~~~)")
_HEADER = re.compile(r"^\s*#")
_CHECKLIST = re.compile(r"^\s*-\s*\[[ xX]\]\s*")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_REF = re.compile(r"\[\[[^\]\n]+\]\]")
_URL = re.compile(r"https?://\S+")


def _strip_noise(body: str) -> str:
    """Return only the "real prose" portion of a markdown body."""
    out: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or _HEADER.match(line):
            continue
        line = _CHECKLIST.sub("", line)
        line = _REF.sub(" ", line)
        line = _URL.sub(" ", line)
        line = _INLINE_CODE.sub(" ", line)
        out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Candidate extraction.
# ---------------------------------------------------------------------------

# Multi-word Title-Case: 2+ words, each starting upper-case, separated by
# single spaces. "WebSocket Hub", "OAuth Token", "Project Shell".
_MULTIWORD_TITLE = re.compile(r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)+\b")

# Determiners / pronouns that capitalise at sentence start and pollute
# multi-word matches ("The WebSocket Hub" → strip "The"). Stripped from the
# *front* of a match only; mid-phrase is fine.
_LEADING_DETERMINERS = frozenset(
    {
        "a",
        "an",
        "the",
        "this",
        "that",
        "these",
        "those",
        "our",
        "their",
        "your",
        "my",
        "his",
        "her",
        "its",
        "we",
        "they",
        "i",
        "you",
        "it",
        "if",
        "when",
        "while",
        "where",
        "every",
        "each",
        "any",
        "some",
        "all",
        "no",
        "for",
        "and",
        "or",
        "but",
        "so",
        "with",
        "without",
        "to",
        "from",
        "into",
    }
)

# kebab-case identifier — at least one hyphen, lowercase letters/digits.
# Avoids matching dashes used as punctuation (e.g. "long-form" inside a
# sentence still matches; that's fine — the strong signal then bumps it
# into the report).
_KEBAB = re.compile(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)+\b")


@dataclass
class _Candidate:
    """One candidate phrase, accumulated across issues."""

    norm: str  # lower-cased, hyphen-form for matching against nodes
    display: str  # original-case form (first occurrence, for display)
    is_kebab: bool
    issue_counts: dict[str, int] = field(default_factory=dict)

    @property
    def cross_issue_freq(self) -> int:
        return len(self.issue_counts)

    @property
    def max_within_issue(self) -> int:
        return max(self.issue_counts.values(), default=0)

    @property
    def total(self) -> int:
        return sum(self.issue_counts.values())


def _strip_leading_determiner(phrase: str) -> str | None:
    """Remove a leading determiner ("The", "A", …) and return the result.

    Returns None if what's left isn't multi-word.
    """
    words = phrase.split()
    if words and words[0].lower() in _LEADING_DETERMINERS:
        words = words[1:]
    if len(words) < 2:
        return None
    return " ".join(words)


def _extract_candidates(prose: str) -> list[tuple[str, bool]]:
    """Return raw candidate strings from prose, with `is_kebab` flag."""
    out: list[tuple[str, bool]] = []
    for m in _MULTIWORD_TITLE.findall(prose):
        cleaned = _strip_leading_determiner(m)
        if cleaned is not None:
            out.append((cleaned, False))
    for m in _KEBAB.findall(prose):
        out.append((m, True))
    return out


# ---------------------------------------------------------------------------
# Node index (for filtering).
# ---------------------------------------------------------------------------


def _build_node_index(project_dir) -> set[str]:
    """Set of normalised node identifiers for fast membership checks.

    For every node we add its id and its name (both lower-cased), plus
    space/hyphen-flipped variants so "Project Shell" matches the
    `project-shell` node id without an extra fuzzy step.
    """
    idx: set[str] = set()
    for n in list_nodes(project_dir):
        for raw in (n.id, n.name):
            if not raw:
                continue
            lower = raw.lower()
            idx.add(lower)
            idx.add(lower.replace(" ", "-"))
            idx.add(lower.replace("-", " "))
    return idx


# ---------------------------------------------------------------------------
# Scoring + reporting.
# ---------------------------------------------------------------------------


def _passes_signal_threshold(c: _Candidate) -> bool:
    """Return True if the candidate's signals are strong enough to report."""
    if c.is_kebab:
        # kebab-case in prose is rare and almost always a missing-bracket ref.
        return True
    if c.cross_issue_freq >= MIN_CROSS_ISSUE_FREQ:
        return True
    if c.max_within_issue >= MIN_WITHIN_ISSUE_FREQ:
        return True
    return False


def _signal_label(c: _Candidate) -> str:
    """Human-readable label for which signals fired (for the message)."""
    bits: list[str] = []
    if c.is_kebab:
        bits.append("kebab-case (likely missing `[[…]]` brackets)")
    if c.cross_issue_freq >= MIN_CROSS_ISSUE_FREQ:
        bits.append(f"cross-issue: {c.cross_issue_freq} issues")
    if c.max_within_issue >= MIN_WITHIN_ISSUE_FREQ:
        bits.append(f"within-issue: {c.max_within_issue}× in one issue")
    return "; ".join(bits) or "weak"


def _fix_hint(c: _Candidate) -> str:
    if c.is_kebab:
        return (
            f"Create a node for {c.display!r} (looks like a node id), or add "
            f"the term to lint/concept-allowlist.yaml with a reason."
        )
    return (
        f"Add a node for {c.display!r}, alias it on an existing node, or add "
        f"it to lint/concept-allowlist.yaml with a reason."
    )


# ---------------------------------------------------------------------------
# Rule entry point.
# ---------------------------------------------------------------------------


@register_rule(
    stage="scoping",
    code="lint/concept_drift",
    severity="warning",
)
def _check(ctx):
    nodes = _build_node_index(ctx.project_dir)
    allowlist = load_concept_allowlist(ctx.project_dir)

    # Pass 1: per-issue → list of (norm, display, is_kebab, count).
    per_issue: dict[str, dict[str, _Candidate]] = defaultdict(dict)
    for issue in list_issues(ctx.project_dir):
        prose = _strip_noise(f"{issue.title or ''}\n{issue.body or ''}")
        for raw, is_kebab in _extract_candidates(prose):
            norm = raw.lower()
            if norm in allowlist or norm in nodes:
                continue
            # Treat "websocket hub" and "websocket-hub" as the same term so
            # cross-issue counts aggregate across both forms.
            canon = norm.replace(" ", "-")
            if canon in allowlist or canon in nodes:
                continue
            slot = per_issue[issue.id].get(canon)
            if slot is None:
                slot = _Candidate(norm=canon, display=raw, is_kebab=is_kebab)
                per_issue[issue.id][canon] = slot
            slot.issue_counts[issue.id] = slot.issue_counts.get(issue.id, 0) + 1

    # Pass 2: roll up cross-issue counts.
    by_term: dict[str, _Candidate] = {}
    for cands in per_issue.values():
        for canon, c in cands.items():
            agg = by_term.get(canon)
            if agg is None:
                agg = _Candidate(norm=canon, display=c.display, is_kebab=c.is_kebab)
                by_term[canon] = agg
            for iid, count in c.issue_counts.items():
                agg.issue_counts[iid] = agg.issue_counts.get(iid, 0) + count

    # Pass 3: emit findings, capped per-issue.
    per_issue_emitted: dict[str, int] = defaultdict(int)
    # Stable order: by signal strength then term, so the top-N cap is
    # deterministic.
    for canon in sorted(
        by_term,
        key=lambda k: (-by_term[k].total, -by_term[k].cross_issue_freq, k),
    ):
        c = by_term[canon]
        if not _passes_signal_threshold(c):
            continue
        for issue_id in sorted(c.issue_counts):
            if per_issue_emitted[issue_id] >= MAX_FINDINGS_PER_ISSUE:
                continue
            per_issue_emitted[issue_id] += 1
            yield LintFinding(
                code="lint/concept_drift",
                severity="warning",
                message=(
                    f"issue {issue_id}: {c.display!r} looks like a load-bearing "
                    f"concept ({_signal_label(c)}) but isn't covered by any "
                    f"node."
                ),
                file=f"issues/{issue_id}/issue.yaml",
                fix_hint=_fix_hint(c),
            )
