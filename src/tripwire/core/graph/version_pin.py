"""Pin-syntax helpers for `[[id@vN]]` references (KUI-126 / A1).

A bare reference `[[id]]` resolves to the latest version of the
target. The pinned form `[[id@vN]]` resolves to the specific
integer version `N`. The pin is parsed from the captured slug:

    parse_pin("user-model")        → ("user-model", None)
    parse_pin("user-model@v3")     → ("user-model", 3)
    parse_pin("user-model@vfoo")   → ("user-model@vfoo", None)

Malformed pins (`@v` followed by anything other than digits) are
treated as plain ids — callers can warn if needed. This is
forward-compat: the parser must not raise on prose that happens to
contain a literal `@`.
"""

from __future__ import annotations

import re

PIN_PATTERN = re.compile(r"^(?P<id>[a-z][a-z0-9-]*)@v(?P<version>\d+)$")


def parse_pin(text: str) -> tuple[str, int | None]:
    """Split a slug into ``(id, version_or_None)``.

    For a bare slug, returns ``(slug, None)``. For a pinned slug like
    ``"user-model@v3"``, returns ``("user-model", 3)``. Malformed pins
    pass through as the literal text with no version.
    """
    m = PIN_PATTERN.match(text)
    if m is None:
        return text, None
    return m.group("id"), int(m.group("version"))


def format_pin(node_id: str, version: int | None) -> str:
    """Render a pin reference (no brackets).

    ``format_pin("user-model", None)`` → ``"user-model"``
    ``format_pin("user-model", 3)``     → ``"user-model@v3"``
    """
    if version is None:
        return node_id
    return f"{node_id}@v{version}"


__all__ = ["PIN_PATTERN", "format_pin", "parse_pin"]
