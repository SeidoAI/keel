"""Orchestration-pattern route (KUI-33).

One read-only endpoint::

    GET /api/projects/{project_id}/orchestration/pattern

Returns the project-wide :class:`OrchestrationPattern` resolved by the
service. Session-scoped overrides are deferred to a future endpoint
under `/sessions/{sid}/orchestration/pattern` — this route is
project-level only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from tripwire.ui.dependencies import ProjectContext, get_project
from tripwire.ui.routes._common import envelope_exception
from tripwire.ui.services.orchestration_service import (
    OrchestrationPattern,
    get_active_pattern,
)

router = APIRouter(
    prefix="/api/projects/{project_id}/orchestration",
    tags=["orchestration"],
)


@router.get("/pattern", response_model=OrchestrationPattern)
async def get_orchestration_pattern(
    project: ProjectContext = Depends(get_project),  # noqa: B008
) -> OrchestrationPattern:
    try:
        return get_active_pattern(project.project_dir)
    except FileNotFoundError as exc:
        raise envelope_exception(
            404,
            code="orchestration/pattern_missing",
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        # Service raises ValueError on YAML parse errors / non-mapping
        # payloads. Surface as 500 with a clean envelope so the frontend
        # can show an actionable message rather than a raw traceback.
        raise envelope_exception(
            500,
            code="orchestration/pattern_invalid",
            detail=str(exc),
        ) from exc
