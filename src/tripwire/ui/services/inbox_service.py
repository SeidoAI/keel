"""Inbox read + resolve service.

Walks ``<project>/inbox/*.md`` and surfaces the parsed entries to
the dashboard. The PM agent writes entries directly via Write tool;
this service is read-only except for ``resolve_inbox_entry`` which
flips the lifecycle flag and re-saves the file.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from tripwire.core import paths
from tripwire.core.parser import ParseError, parse_frontmatter_body
from tripwire.models.inbox import InboxEntry, InboxReference

logger = logging.getLogger("tripwire.ui.services.inbox_service")


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class InboxItem(BaseModel):
    """Lightweight inbox descriptor for list views — flattens the
    references into ``ReferenceDescriptor``s the frontend can render
    directly without re-parsing the union."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    id: str
    bucket: str  # "blocked" | "fyi"
    title: str
    body: str = ""
    author: str
    created_at: datetime
    references: list[dict] = Field(default_factory=list)
    escalation_reason: str | None = None
    resolved: bool = False
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class InboxResolveRequest(BaseModel):
    """POST body for ``/inbox/<id>/resolve``."""

    model_config = ConfigDict(extra="forbid")

    resolved_by: str | None = None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_entry_file(path: Path) -> InboxEntry | None:
    """Parse a single inbox file. Returns ``None`` on parse error
    (and logs) rather than raising — one malformed file shouldn't
    take down the whole list endpoint."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("inbox: cannot read %s: %s", path, exc)
        return None
    try:
        frontmatter, body = parse_frontmatter_body(text)
    except ParseError as exc:
        logger.warning("inbox: cannot parse %s: %s", path, exc)
        return None
    try:
        return InboxEntry.model_validate({**frontmatter, "body": body})
    except Exception as exc:  # pydantic ValidationError or schema mismatch
        logger.warning("inbox: invalid frontmatter in %s: %s", path, exc)
        return None


def _to_item(entry: InboxEntry) -> InboxItem:
    """Flatten an InboxEntry into the wire-friendly InboxItem DTO.
    The references union becomes a list of dicts (each with the
    discriminator key + payload), keeping the JSON shape stable
    even as we add new reference types."""
    refs = [_ref_to_dict(r) for r in entry.references]
    return InboxItem(
        id=entry.id,
        bucket=entry.bucket,
        title=entry.title,
        body=entry.body,
        author=entry.author,
        created_at=entry.created_at,
        references=refs,
        escalation_reason=entry.escalation_reason,
        resolved=entry.resolved,
        resolved_at=entry.resolved_at,
        resolved_by=entry.resolved_by,
    )


def _ref_to_dict(ref: InboxReference) -> dict:
    """Serialise a reference to a dict the frontend can switch on by
    looking at its keys (e.g. presence of ``issue`` vs ``session``).
    Drops Nones so optional fields like ``version`` don't appear when
    omitted."""
    return ref.model_dump(exclude_none=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_inbox(
    project_dir: Path,
    bucket: str | None = None,
    resolved: bool | None = None,
) -> list[InboxItem]:
    """Return all inbox entries, optionally filtered by bucket /
    resolved state. Sorted newest-first by ``created_at``."""
    root = paths.inbox_dir(project_dir)
    if not root.is_dir():
        return []
    items: list[InboxItem] = []
    for path in sorted(root.glob("*.md")):
        entry = _load_entry_file(path)
        if entry is None:
            continue
        if bucket is not None and entry.bucket != bucket:
            continue
        if resolved is not None and entry.resolved != resolved:
            continue
        items.append(_to_item(entry))
    items.sort(key=lambda i: i.created_at, reverse=True)
    return items


def get_inbox_entry(project_dir: Path, entry_id: str) -> InboxItem | None:
    """Return one entry by id, or ``None`` when missing."""
    path = paths.inbox_entry_path(project_dir, entry_id)
    if not path.is_file():
        return None
    entry = _load_entry_file(path)
    return _to_item(entry) if entry is not None else None


def resolve_inbox_entry(
    project_dir: Path,
    entry_id: str,
    resolved_by: str | None = None,
) -> InboxItem | None:
    """Mark an entry resolved + write back atomically. Returns the
    updated item, or ``None`` when the entry doesn't exist."""
    path = paths.inbox_entry_path(project_dir, entry_id)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    try:
        frontmatter, body = parse_frontmatter_body(text)
    except ParseError as exc:
        logger.warning("inbox: cannot parse %s for resolve: %s", path, exc)
        return None
    frontmatter["resolved"] = True
    frontmatter["resolved_at"] = datetime.now(UTC).isoformat()
    frontmatter["resolved_by"] = resolved_by or "ui-user"
    new_text = _serialise_entry(frontmatter, body)
    # Atomic write: write to a sibling tempfile, then rename. This
    # avoids the file watcher seeing a half-written file mid-update.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    tmp.replace(path)
    return get_inbox_entry(project_dir, entry_id)


def _serialise_entry(frontmatter: dict, body: str) -> str:
    """Round-trip the frontmatter dict back to YAML + reattach the
    markdown body. Matches the canonical ``---\\n<yaml>\\n---\\n<body>``
    shape produced by the PM agent's writes."""
    import yaml

    yaml_text = yaml.safe_dump(frontmatter, sort_keys=False, default_flow_style=False).strip()
    return f"---\n{yaml_text}\n---\n{body}"
