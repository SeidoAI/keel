"""Shared route parameter validators."""

from __future__ import annotations

import re

from tripwire.ui.routes._common import envelope_exception

_SESSION_ID_PATTERN = r"^[a-z][a-z0-9-]*$"
_SESSION_ID_RE = re.compile(_SESSION_ID_PATTERN)


def ensure_session_id(sid: str) -> None:
    """Reject path-like or non-canonical session IDs before service calls."""
    if not _SESSION_ID_RE.match(sid):
        raise envelope_exception(
            400,
            code="session/bad_slug",
            detail=(
                f"Session id {sid!r} does not match {_SESSION_ID_PATTERN} "
                "(lowercase letter first, then alphanumerics or hyphens)."
            ),
        )


__all__ = ["ensure_session_id"]
