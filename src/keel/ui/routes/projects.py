"""Project listing and detail routes.

Endpoints filled by their respective route issues.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects() -> None:
    """List discovered projects."""
    raise HTTPException(status_code=501, detail="Not yet implemented")


@router.get("/{project_id}")
async def get_project(project_id: str) -> None:
    """Get project detail."""
    raise HTTPException(status_code=501, detail="Not yet implemented")
