"""v0.7.9 §A9 — self-review.md on main ⇒ pm-response.md on main.

Catches the "PM forgot to respond" state: a session whose author
finished and pushed self-review, but the PM never wrote the closing
response. Triggered by the presence of self-review.md on origin/main
for any known session, regardless of session.status.

Same offline-degradation pattern as
``done_implies_artifacts_on_main``: emit one ``main_unavailable``
warning if origin/main is unreadable and skip per-session checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tripwire.core.git_helpers import MainTreeUnavailable, list_paths_on_main
from tripwire.core.store import PROJECT_CONFIG_FILENAME

if TYPE_CHECKING:
    from tripwire.core.validator import CheckResult, ValidationContext


def check(ctx: ValidationContext) -> list[CheckResult]:
    from tripwire.core.validator import CheckResult

    if not ctx.sessions:
        return []

    try:
        on_main = list_paths_on_main(ctx.project_dir)
    except MainTreeUnavailable as exc:
        return [
            CheckResult(
                code="self_review_implies_pm_response/main_unavailable",
                severity="warning",
                file=PROJECT_CONFIG_FILENAME,
                message=(
                    f"Cannot read origin/main; "
                    f"`self-review ⇒ pm-response` rule unverified ({exc})."
                ),
                fix_hint=(
                    "Run `git fetch origin` in the project tracking repo, "
                    "then re-run validate."
                ),
            )
        ]

    results: list[CheckResult] = []
    for entity in ctx.sessions:
        sid = entity.model.id
        self_review = f"sessions/{sid}/self-review.md"
        pm_response = f"sessions/{sid}/pm-response.md"
        if self_review not in on_main:
            continue
        if pm_response in on_main:
            continue
        results.append(
            CheckResult(
                code="self_review_implies_pm_response/missing_pm_response",
                severity="error",
                file=entity.rel_path,
                message=(
                    f"Session {sid!r} has self-review.md on origin/main "
                    f"but {pm_response!r} is missing — the PM has not "
                    f"closed the loop."
                ),
                fix_hint=(
                    f"Author and commit {pm_response} on the project "
                    f"tracking branch, then merge to main."
                ),
            )
        )

    return results
