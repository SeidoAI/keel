"""Session listing and detail routes (KUI-30).

Two read-only endpoints under `/api/projects/{project_id}/sessions`:

    GET  /                return list of `SessionSummary` (optional status filter)
    GET  /{sid}           return full `SessionDetail` including plan_md,
                           artifact_status, task_progress

Finalising a session lives under the actions router (KUI-34); there is
no mutation in this module in v1.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from tripwire.ui.dependencies import ProjectContext, get_project
from tripwire.ui.routes._common import envelope_exception
from tripwire.ui.routes._params import ensure_session_id
from tripwire.ui.services.action_service import (
    SessionResult,
    SessionRuntimeError,
    SessionStatusError,
    pause_session,
)
from tripwire.ui.services.session_service import (
    SessionDetail,
    SessionSummary,
)
from tripwire.ui.services.session_service import (
    get_session as svc_get_session,
)
from tripwire.ui.services.session_service import (
    list_sessions as svc_list_sessions,
)

router = APIRouter(prefix="/api/projects/{project_id}/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    project: ProjectContext = Depends(get_project),  # noqa: B008
    status: str | None = Query(None, description="Filter by session status"),
) -> list[SessionSummary]:
    return svc_list_sessions(project.project_dir, status=status)


@router.get("/{sid}", response_model=SessionDetail)
async def get_session(
    sid: str,
    project: ProjectContext = Depends(get_project),  # noqa: B008
) -> SessionDetail:
    ensure_session_id(sid)
    try:
        return svc_get_session(project.project_dir, sid)
    except FileNotFoundError as exc:
        raise envelope_exception(
            404,
            code="session/not_found",
            detail=f"Session {sid!r} not found in this project.",
        ) from exc


@router.post("/{sid}/pause", response_model=SessionResult)
async def pause_session_route(
    sid: str,
    project: ProjectContext = Depends(get_project),  # noqa: B008
) -> SessionResult:
    """KUI-107 INTERVENE — pause an executing session via its runtime.

    Thin HTTP face on :func:`tripwire.ui.services.action_service.pause_session`.
    No new server-side semantics: same status guard, same dead-PID
    fall-through to ``failed``, same audit trail as the CLI's
    ``tripwire session pause``.
    """
    ensure_session_id(sid)
    try:
        return pause_session(project.project_dir, sid)
    except FileNotFoundError as exc:
        raise envelope_exception(
            404,
            code="session/not_found",
            detail=f"Session {sid!r} not found in this project.",
        ) from exc
    except SessionStatusError as exc:
        raise envelope_exception(
            409,
            code="session/bad_status",
            detail=str(exc),
        ) from exc
    except SessionRuntimeError as exc:
        raise envelope_exception(
            409,
            code="session/runtime_refused",
            detail=str(exc),
        ) from exc
