"""Project listing and detail routes (KUI-26).

Read-only endpoints. Both are thin wrappers over
:mod:`tripwire.ui.services.project_service`; translation of service
exceptions to HTTP status codes happens here, nothing else.
"""

from __future__ import annotations

from fastapi import APIRouter, Path

from tripwire.ui.routes._common import envelope_exception
from tripwire.ui.services.project_service import (
    ProjectDetail,
    ProjectSummary,
    get_project,
    list_projects,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummary])
async def list_all_projects() -> list[ProjectSummary]:
    """Return every discoverable project as a :class:`ProjectSummary`."""
    return list_projects()


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project_detail(
    project_id: str = Path(..., pattern=r"^[a-f0-9]{12}$"),
) -> ProjectDetail:
    """Return full :class:`ProjectDetail` for *project_id*.

    Translates :class:`KeyError` from the service (unknown project id)
    to a 404 envelope with code ``project/not_found``.
    """
    try:
        return get_project(project_id)
    except KeyError as exc:
        raise envelope_exception(
            404,
            code="project/not_found",
            detail=f"Project {project_id!r} not found",
        ) from exc
