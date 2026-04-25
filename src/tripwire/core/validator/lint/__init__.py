"""Project-state lint rules (v0.7.9 §A9).

Each module in this package exports a single ``check(ctx) -> list[CheckResult]``
function. ``tripwire.core.validator.__init__`` imports ``LINT_CHECKS``
from here and appends each entry to ``ALL_CHECKS``.

To add a new rule:
1. Create ``<my_rule>.py`` with ``def check(ctx): ...``
2. Append ``<my_rule>.check`` to ``LINT_CHECKS`` below.

That's it. No registry, no decorators.

(``pm_response_followups_resolve`` is defined as an in-file function on
``validator/__init__.py`` rather than a module here — it landed via
KUI-86 with tighter coupling to the new pm-response.yaml format and
its parser helpers in ``session_review_artifacts``.)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tripwire.core.validator import CheckResult, ValidationContext

from . import (
    done_implies_artifacts_on_main,
    no_orphan_proj_branches,
    self_review_implies_pm_response,
    worktree_paths_unique,
)

CheckFunc = Callable[["ValidationContext"], "list[CheckResult]"]

LINT_CHECKS: list[CheckFunc] = [
    done_implies_artifacts_on_main.check,
    self_review_implies_pm_response.check,
    worktree_paths_unique.check,
    no_orphan_proj_branches.check,
]
