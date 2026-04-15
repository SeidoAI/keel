"""lint/unpushed_promotion_candidates — local nodes marked
``scope: workspace`` that haven't been pushed up yet.

In v0.6a ``origin``/``scope`` aren't part of the node schema (they
ship in v0.6b with the workspace primitive). The rule therefore
no-ops for normal nodes; it reads the fields via ``getattr`` with
a ``local`` default so it keeps working once v0.6b lands and nodes
start carrying them.

Severity: info until a workspace is linked, then warning (v0.6b
will set that second half up). v0.6a always emits info.
"""

from __future__ import annotations

from keel.core.linter import LintFinding, register_rule
from keel.core.node_store import list_nodes


@register_rule(
    stage="scoping",
    code="lint/unpushed_promotion_candidates",
    severity="info",
)
def _check(ctx):
    for n in list_nodes(ctx.project_dir):
        origin = getattr(n, "origin", "local")
        scope = getattr(n, "scope", "local")
        if origin == "local" and scope == "workspace":
            yield LintFinding(
                code="lint/unpushed_promotion_candidates",
                severity="info",
                message=(
                    f"node {n.id} is local-origin with scope=workspace "
                    "— promotion candidate."
                ),
                file=f"nodes/{n.id}.yaml",
                fix_hint=(
                    "Run /pm-project-sync (v0.6b) to push, or mark "
                    "scope=local if it shouldn't flow upstream."
                ),
            )
