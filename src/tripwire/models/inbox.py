"""Inbox entry model.

An inbox entry is a structured escalation written by the PM agent
(and only the PM agent) when something needs the human user's
attention or knowledge. Two buckets:

- ``blocked`` — interruptive. Something is paused or about to drift
  without a human decision. Demands action.
- ``fyi`` — digest. A decision was made or work completed; the
  human should know in case they disagree.

Storage is one markdown-with-YAML-frontmatter file per entry at
``<project>/inbox/<id>.md``. The PM agent writes the file directly;
the file watcher emits a ``FileChangedEvent`` and the dashboard
re-renders. No messaging layer is involved — file write is the
transport.

See ``docs/philosophy.md`` for the design rationale (two-bucket
attention model, PM agent as attention curator).
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

InboxBucket = Literal["blocked", "fyi"]


class InboxIssueRef(BaseModel):
    """Reference to an issue (concrete) — uses the issue key like SEI-42."""

    model_config = ConfigDict(extra="forbid")

    issue: str


class InboxEpicRef(BaseModel):
    """Reference to an epic — typed separately from issue for renderer
    clarity (epics carry the ``type/epic`` label and have a different
    detail screen)."""

    model_config = ConfigDict(extra="forbid")

    epic: str


class InboxSessionRef(BaseModel):
    """Reference to a session — uses the slug id like ``storage-impl``."""

    model_config = ConfigDict(extra="forbid")

    session: str


class InboxNodeRef(BaseModel):
    """Reference to a concept node, with optional version pinning.

    The PM agent populates ``version`` at write time so the dashboard
    can warn when the node has drifted ("viewing v3, latest is v5").
    Resolving the inbox entry implies acknowledgment of the version
    context. Omit ``version`` for live "current state" links.
    """

    model_config = ConfigDict(extra="forbid")

    node: str
    version: str | None = None


class InboxArtifactRef(BaseModel):
    """Reference to a per-session artifact (plan.md, self-review.md, etc.)."""

    model_config = ConfigDict(extra="forbid")

    session: str
    file: str


class InboxCommentRef(BaseModel):
    """Reference to a comment on an issue."""

    model_config = ConfigDict(extra="forbid")

    issue: str
    id: str


class InboxPRRef(BaseModel):
    """Reference to an external GitHub PR. Format: ``owner/repo/<number>``."""

    model_config = ConfigDict(extra="forbid")

    pr: str


# Order matters for Pydantic discriminated-union resolution: the most
# specific shapes (with two fields) should appear before single-field
# shapes so disambiguation is unambiguous.
InboxReference = (
    InboxArtifactRef
    | InboxCommentRef
    | InboxIssueRef
    | InboxEpicRef
    | InboxSessionRef
    | InboxNodeRef
    | InboxPRRef
)


class InboxEntry(BaseModel):
    """One inbox entry — the YAML frontmatter half of an inbox file.

    The markdown body lives in ``body``; ``parse_frontmatter_body``
    splits the file then this model validates the frontmatter dict
    with ``body`` injected separately.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Identity
    id: str
    uuid: UUID = Field(default_factory=_uuid.uuid4)

    # Provenance
    created_at: datetime
    author: str  # currently always "pm-agent"; future: any agent that has push access

    # Content
    bucket: InboxBucket
    title: str
    body: str = ""

    # First-class entity references; rendered as chips in the UI and
    # validated by the validator (each must resolve to a real entity).
    references: list[InboxReference] = Field(default_factory=list)

    # Seed for future meta-learning — over many resolves we mine
    # which reasons earn fast action vs ignored-then-auto-archived.
    escalation_reason: str | None = None

    # Lifecycle
    resolved: bool = False
    resolved_at: datetime | None = None
    resolved_by: str | None = None
