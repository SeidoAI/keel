"""Inbox routes — list, single-entry read, and resolve.

The inbox is a stream of attention-worthy items the PM agent
escalates to the human user. Two buckets:

- ``blocked`` — needs your input before work continues
- ``fyi`` — decided/done facts you should know

Authoring is PM-agent-only via direct file write to
``<project>/inbox/<id>.md`` — there's no POST-create endpoint
because the agent's natural surface is the filesystem (per the
existing PM-skill convention; same as issues, sessions, nodes).

Reads:
    GET    /                       list with optional ``bucket`` /
                                   ``resolved`` filters
    GET    /{entry_id}              single-entry detail
    POST   /{entry_id}/resolve      flip ``resolved=true`` and stamp
                                   ``resolved_at`` / ``resolved_by``
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from tripwire.ui.dependencies import ProjectContext, get_project
from tripwire.ui.routes._common import envelope_exception
from tripwire.ui.services.inbox_service import (
    InboxItem,
    InboxResolveRequest,
)
from tripwire.ui.services.inbox_service import (
    get_inbox_entry as svc_get_entry,
)
from tripwire.ui.services.inbox_service import (
    list_inbox as svc_list_inbox,
)
from tripwire.ui.services.inbox_service import (
    resolve_inbox_entry as svc_resolve_entry,
)

router = APIRouter(prefix="/api/projects/{project_id}/inbox", tags=["inbox"])


@router.get("", response_model=list[InboxItem])
async def list_inbox(
    project: ProjectContext = Depends(get_project),  # noqa: B008
    bucket: str | None = Query(None, description="Filter by bucket: blocked | fyi"),
    resolved: bool | None = Query(None, description="Filter by resolved state"),
) -> list[InboxItem]:
    return svc_list_inbox(project.project_dir, bucket=bucket, resolved=resolved)


@router.get("/{entry_id}", response_model=InboxItem)
async def get_inbox_entry(
    entry_id: str,
    project: ProjectContext = Depends(get_project),  # noqa: B008
) -> InboxItem:
    item = svc_get_entry(project.project_dir, entry_id)
    if item is None:
        raise envelope_exception(
            404,
            code="inbox/not_found",
            detail=f"Inbox entry {entry_id!r} not found.",
        )
    return item


@router.post("/{entry_id}/resolve", response_model=InboxItem)
async def resolve_inbox_entry(
    entry_id: str,
    body: InboxResolveRequest | None = None,
    project: ProjectContext = Depends(get_project),  # noqa: B008
) -> InboxItem:
    resolved_by = body.resolved_by if body else None
    item = svc_resolve_entry(project.project_dir, entry_id, resolved_by=resolved_by)
    if item is None:
        raise envelope_exception(
            404,
            code="inbox/not_found",
            detail=f"Inbox entry {entry_id!r} not found.",
        )
    return item
