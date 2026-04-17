"""Orchestration-pattern routes.

Endpoints filled by their respective route issues.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/api/projects/{project_id}/orchestration",
    tags=["orchestration"],
)


@router.get("/pattern")
async def get_orchestration_pattern(project_id: str) -> None:
    """Return the orchestration pattern for a project."""
    raise HTTPException(status_code=501, detail="Not yet implemented")
