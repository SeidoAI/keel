"""v0.7.9 §A1 — terminal-success ⇒ required artifacts exist on origin/main.

The correctness contract. For sessions, this rule checks the **flat-
file** layout (``sessions/<sid>/<file>``) used by pre-v0.8 sessions —
post-KUI-110 these are tagged with ``status: legacy_completed``. Modern
``completed`` sessions use the subdir layout
(``sessions/<sid>/artifacts/<file>``) which is exercised by
``check_artifact_presence`` instead. Every required file listed in
``project.yaml.artifact_manifest.session_required`` must be present
on the merged-main snapshot of the project tracking repo
(``origin/main``); "on main" is the only state that counts.

For issues, the rule checks ``status: done`` (issues retained that
terminal value through KUI-110).

Online-first. We don't ``git fetch`` from inside validate (would hit
the network on every run). If ``origin/main`` is unreadable (no remote,
no fetch yet, repo isn't a git checkout), emit a single
``done_implies_artifacts/main_unavailable`` warning and skip the
per-entity checks — the operator can re-run after a fetch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tripwire.core.git_helpers import MainTreeUnavailable, list_paths_on_main
from tripwire.core.store import PROJECT_CONFIG_FILENAME

if TYPE_CHECKING:
    from tripwire.core.validator import CheckResult, ValidationContext


def check(ctx: ValidationContext) -> list[CheckResult]:
    from tripwire.core.validator import CheckResult

    if ctx.project_config is None:
        return []

    done_sessions = [
        e for e in ctx.sessions if e.model.status == "legacy_completed"
    ]
    done_issues = [e for e in ctx.issues if e.model.status == "done"]
    if not done_sessions and not done_issues:
        return []

    try:
        on_main = list_paths_on_main(ctx.project_dir)
    except MainTreeUnavailable as exc:
        return [
            CheckResult(
                code="done_implies_artifacts/main_unavailable",
                severity="warning",
                file=PROJECT_CONFIG_FILENAME,
                message=(
                    f"Cannot read origin/main; `done` ⇒ artifact rule "
                    f"unverified ({exc})."
                ),
                fix_hint=(
                    "Run `git fetch origin` in the project tracking repo, "
                    "then re-run validate. Network-isolated environments "
                    "can ignore this warning."
                ),
            )
        ]

    manifest = ctx.project_config.artifact_manifest
    results: list[CheckResult] = []

    for entity in done_sessions:
        session = entity.model
        for fname in manifest.session_required:
            rel = f"sessions/{session.id}/{fname}"
            if rel in on_main:
                continue
            results.append(
                CheckResult(
                    code="done_implies_artifacts/missing_on_main",
                    severity="error",
                    file=entity.rel_path,
                    message=(
                        f"Session {session.id!r} is `legacy_completed` but "
                        f"required artifact {rel!r} is not on origin/main."
                    ),
                    fix_hint=(
                        f"Commit {rel} to the project tracking branch and "
                        "merge to main, OR transition the session to "
                        "`abandoned` if the work didn't actually complete."
                    ),
                )
            )

    for entity in done_issues:
        issue = entity.model
        for fname in manifest.issue_required:
            rel = f"issues/{issue.id}/{fname}"
            if rel in on_main:
                continue
            results.append(
                CheckResult(
                    code="done_implies_artifacts/missing_on_main",
                    severity="error",
                    file=entity.rel_path,
                    message=(
                        f"Issue {issue.id!r} is `done` but required "
                        f"artifact {rel!r} is not on origin/main."
                    ),
                    fix_hint=(
                        f"Commit {rel} to the project tracking branch and "
                        "merge to main, OR transition the issue back to "
                        "an in-progress status."
                    ),
                )
            )

    return results
