"""v0.7.9 §A9 — every local ``proj/<sid>`` branch needs a matching session.

Reads local refs under ``refs/heads/proj/`` from the project tracking
repo and flags any whose ``<sid>`` part has no matching session.yaml.
Catches the "spawn created a branch but the agent never used it"
state — orphan refs that accumulate over time and clutter the repo.

Local branches only (not remote). The check runs in
``ctx.project_dir`` since that's where ``project.yaml`` and the
session-tracking branches live.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tripwire.core.validator import CheckResult, ValidationContext


def local_proj_branches(repo_dir: Path) -> list[str]:
    """Return local branch names under ``refs/heads/proj/``.

    Degrades to ``[]`` on any failure (not a git repo, no proj/*
    branches, etc.). The validator must be local-first and silent on
    missing prerequisites.
    """
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_dir),
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/heads/proj/",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def check(ctx: ValidationContext) -> list[CheckResult]:
    from tripwire.core.validator import CheckResult

    branches = local_proj_branches(ctx.project_dir)
    if not branches:
        return []

    known_session_ids = {entity.model.id for entity in ctx.sessions}
    results: list[CheckResult] = []
    for branch in branches:
        sid = branch.removeprefix("proj/")
        if sid in known_session_ids:
            continue
        results.append(
            CheckResult(
                code="no_orphan_proj_branches/orphan",
                severity="error",
                message=(
                    f"Local branch {branch!r} has no matching session "
                    f"(no sessions/{sid}/session.yaml). The branch was "
                    f"likely created by a spawn whose agent never used it."
                ),
                fix_hint=(
                    f"Either restore the missing sessions/{sid}/ artifacts "
                    f"from history, OR delete the orphan branch with "
                    f"`git branch -D {branch}`."
                ),
            )
        )

    return results
