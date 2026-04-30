"""Pattern aggregation over pm-review verdicts (KUI-151 / J2).

Reads ``pm_review.completed`` events from the workflow events log
across all sessions and surfaces recurring failure patterns —
"``schema`` failed in 4/5 last sessions" — so the PM can spot
systemic process gaps rather than re-flagging the same finding on
each session.

Read-only. Never touches the events log or the artifacts; the events
log is the source of truth and aggregation is a pure projection over
it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from tripwire.core.events.log import read_events


@dataclass(frozen=True)
class CheckPattern:
    """One per-check aggregation row."""

    check: str
    fail_count: int
    total: int

    @property
    def fail_rate(self) -> float:
        return self.fail_count / self.total if self.total else 0.0


@dataclass(frozen=True)
class AggregateReport:
    """The full pattern report."""

    total_reviews: int
    outcome_counts: dict[str, int] = field(default_factory=dict)
    patterns: list[CheckPattern] = field(default_factory=list)


def aggregate_patterns(
    project_dir: Path,
    *,
    min_fail_count: int = 1,
    workflow_id: str = "pm-review",
) -> AggregateReport:
    """Walk the events log; aggregate ``pm_review.completed`` rows.

    ``min_fail_count`` drops checks that have failed less than that
    many times across all reviews — a useful filter for "what's
    *recurring*?" vs "what failed once?". The default (``1``) keeps
    every check that failed at least once.

    The patterns list is sorted by ``fail_count`` descending so the
    biggest signal lands on top.
    """
    fail_counter: Counter[str] = Counter()
    outcome_counter: Counter[str] = Counter()
    total = 0
    for row in read_events(
        project_dir, workflow=workflow_id, event="pm_review.completed"
    ):
        total += 1
        details = row.get("details") or {}
        outcome = details.get("outcome")
        if isinstance(outcome, str):
            outcome_counter[outcome] += 1
        failed = details.get("failed_checks") or []
        if isinstance(failed, list):
            for name in failed:
                if isinstance(name, str):
                    fail_counter[name] += 1

    patterns = [
        CheckPattern(check=name, fail_count=count, total=total)
        for name, count in fail_counter.most_common()
        if count >= min_fail_count
    ]
    return AggregateReport(
        total_reviews=total,
        outcome_counts=dict(outcome_counter),
        patterns=patterns,
    )


__all__ = ["AggregateReport", "CheckPattern", "aggregate_patterns"]
