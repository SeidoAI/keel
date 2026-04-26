"""Workflow graph route (KUI-100).

Single endpoint:

    GET  /api/projects/{project_id}/workflow

Returns the full orchestration graph (lifecycle stations, validators,
tripwires, connectors, artifacts) for the Workflow Map UI. PM-mode
header (`X-Tripwire-Role: pm`) controls whether tripwire `prompt_revealed`
fields are populated. See `docs/specs/2026-04-26-v08-handoff.md` §2.1.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from tripwire.ui.dependencies import ProjectContext, get_project
from tripwire.ui.services.role_gate import is_pm
from tripwire.ui.services.workflow_service import build_workflow

router = APIRouter(prefix="/api/projects/{project_id}", tags=["workflow"])


@router.get("/workflow")
async def get_workflow_route(
    request: Request,
    project: ProjectContext = Depends(get_project),  # noqa: B008
) -> dict[str, Any]:
    """Return the orchestration graph, with PM-mode redaction applied."""
    return build_workflow(
        project.project_dir,
        project_id=project.project_id,
        is_pm_role=is_pm(request),
    )
