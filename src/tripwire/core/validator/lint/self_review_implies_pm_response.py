"""Stub — implementation lands in the green step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tripwire.core.git_helpers import (  # noqa: F401  (used by tests via monkeypatch)
    list_paths_on_main,
)

if TYPE_CHECKING:
    from tripwire.core.validator import CheckResult, ValidationContext


def check(ctx: ValidationContext) -> list[CheckResult]:
    return []
