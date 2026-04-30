"""Extract `[[node-id]]` references from Markdown bodies.

Edges in the concept graph are emergent: an issue body that says
`[[user-model]]` creates an edge from the issue to the `user-model` node
without any separate edge file. This module pulls those references out of
prose and returns them as a list.

Code blocks are explicitly skipped — `[[foo]]` inside a fenced code block
is not a reference (it's literal code or example output).
"""

from __future__ import annotations

import re

# A reference is `[[id]]` (latest version) or `[[id@vN]]` (pinned to
# integer version `N`). The strict slug rule means random
# `[[words like this]]` in prose are NOT picked up — only things that
# look like real node ids. The optional pin annotation must be a
# decimal integer; `@vfoo` is rejected.
REFERENCE_PATTERN = re.compile(r"\[\[([a-z][a-z0-9-]*)(?:@v(\d+))?\]\]")

# Lines that toggle a fenced code block. We use a permissive opening rule:
# any line whose stripped form starts with three backticks (or three tildes)
# enters a code block; the same toggles it off.
FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")


def extract_references(body: str) -> list[str]:
    """Return all bare `[[node-id]]` references found in `body`, in order.

    Pinned references (`[[id@vN]]`) collapse to their bare id for
    backwards compat with v0.9 callers (validator, cache, UI) that
    don't yet care about the pin annotation. Use
    :func:`extract_references_with_pins` to get the (id, version)
    pairs.

    Duplicates are preserved (an issue that mentions `[[user-model]]`
    twice yields it twice). Lines inside fenced code blocks are
    ignored.
    """
    refs: list[str] = []
    in_fence = False

    for line in body.splitlines():
        if FENCE_PATTERN.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for slug, _version in REFERENCE_PATTERN.findall(line):
            refs.append(slug)

    return refs


def extract_references_with_pins(body: str) -> list[tuple[str, int | None]]:
    """Like :func:`extract_references` but also returns the pin version.

    Each entry is a ``(node_id, version)`` tuple. ``version`` is None
    for bare ``[[id]]`` references and an integer for pinned ones.
    """
    pairs: list[tuple[str, int | None]] = []
    in_fence = False

    for line in body.splitlines():
        if FENCE_PATTERN.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for slug, version in REFERENCE_PATTERN.findall(line):
            pairs.append((slug, int(version) if version else None))

    return pairs


def replace_references(
    body: str,
    resolver: callable,  # type: ignore[valid-type]
) -> str:
    """Replace every `[[node-id]]` in `body` with `resolver(node_id)`.

    The resolver is called with the bare node id (no brackets) and should
    return the replacement string. Lines inside fenced code blocks are left
    untouched.

    Useful for the UI to render references as links, or for the validator's
    `--fix` to rewrite collided ids in place.
    """
    out_lines: list[str] = []
    in_fence = False

    for line in body.splitlines(keepends=True):
        if FENCE_PATTERN.match(line):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue
        out_lines.append(REFERENCE_PATTERN.sub(lambda m: resolver(m.group(1)), line))

    return "".join(out_lines)
