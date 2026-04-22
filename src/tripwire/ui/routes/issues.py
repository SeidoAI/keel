"""Issue listing, detail, mutation, and validation routes (KUI-27).

Four endpoints under `/api/projects/{project_id}`:

    GET    /issues                          list (filters)
    GET    /issues/{key}                    single detail
    PATCH  /issues/{key}                    partial update
    POST   /issues/{key}/validate           issue-scoped validation

All endpoints are thin wrappers over the service layer. Business logic —
transition checks, label validation, audit logging — stays in the
service; the route only translates service exceptions to HTTP envelopes.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, Query

from tripwire.ui.dependencies import ProjectContext, get_project
from tripwire.ui.routes._common import envelope_exception
from tripwire.ui.services.issue_mutation_service import (
    IssuePatch,
    update_issue_fields,
)
from tripwire.ui.services.issue_service import (
    IssueDetail,
    IssueFilters,
    IssueSummary,
)
from tripwire.ui.services.issue_service import (
    get_issue as svc_get_issue,
)
from tripwire.ui.services.issue_service import (
    list_issues as svc_list_issues,
)
from tripwire.ui.services.issue_service import (
    validate_issue as svc_validate_issue,
)

router = APIRouter(prefix="/api/projects/{project_id}", tags=["issues"])


def _ensure_key(project: ProjectContext, key: str) -> None:
    """Validate *key* against the project's `PREFIX-<digits>` pattern."""
    pattern = re.compile(rf"^{re.escape(project.config.key_prefix)}-\d+$")
    if not pattern.match(key):
        raise envelope_exception(
            400,
            code="issue/bad_key",
            detail=(
                f"Issue key {key!r} does not match this project's "
                f"pattern {project.config.key_prefix}-<N>."
            ),
        )


@router.get("/issues", response_model=list[IssueSummary])
async def list_issues(
    project: ProjectContext = Depends(get_project),  # noqa: B008
    status: str | None = Query(None),
    executor: str | None = Query(None),
    label: str | None = Query(None),
    parent: str | None = Query(None),
) -> list[IssueSummary]:
    """Return every issue as a summary, narrowed by optional filters."""
    filters = IssueFilters(status=status, executor=executor, label=label, parent=parent)
    return svc_list_issues(project.project_dir, filters)


@router.get("/issues/{key}", response_model=IssueDetail)
async def get_issue(
    key: str,
    project: ProjectContext = Depends(get_project),  # noqa: B008
) -> IssueDetail:
    _ensure_key(project, key)
    try:
        return svc_get_issue(project.project_dir, key)
    except FileNotFoundError as exc:
        raise envelope_exception(
            404,
            code="issue/not_found",
            detail=f"Issue {key!r} not found in this project.",
        ) from exc


@router.patch("/issues/{key}", response_model=IssueDetail)
async def patch_issue(
    key: str,
    patch: IssuePatch,
    project: ProjectContext = Depends(get_project),  # noqa: B008
) -> IssueDetail:
    _ensure_key(project, key)
    try:
        return update_issue_fields(project.project_dir, key, patch)
    except FileNotFoundError as exc:
        raise envelope_exception(
            404,
            code="issue/not_found",
            detail=f"Issue {key!r} not found in this project.",
        ) from exc
    except ValueError as exc:
        # Invalid transition / invalid enum value / invalid label — the
        # service returns a human-readable message; pass it through so
        # the UI can surface it verbatim.
        raise envelope_exception(
            409,
            code="issue/invalid_transition",
            detail=str(exc),
        ) from exc


@router.post("/issues/{key}/validate")
async def validate_issue(
    key: str,
    project: ProjectContext = Depends(get_project),  # noqa: B008
) -> dict[str, Any]:
    """Run validation for *key* and return the report body.

    Always returns 200 — error/warning counts live inside the body, not
    in the HTTP status. An unknown key returns 404 before we enter the
    validator so the caller doesn't get a misleading empty report.
    """
    _ensure_key(project, key)
    try:
        svc_get_issue(project.project_dir, key)
    except FileNotFoundError as exc:
        raise envelope_exception(
            404,
            code="issue/not_found",
            detail=f"Issue {key!r} not found in this project.",
        ) from exc
    report = svc_validate_issue(project.project_dir, key)
    return report.to_json()
