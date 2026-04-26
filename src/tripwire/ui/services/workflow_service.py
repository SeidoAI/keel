"""Build the `/api/workflow` graph by introspecting registries.

The Workflow Map UI consumes this — see
`docs/specs/2026-04-26-v08-handoff.md` §2.1 for the response shape and
the layout-hint contract (no absolute coordinates; each entity carries
the station it attaches to so the UI can lay it out).

The `validators` and `tripwires` lists are derived from real registries:
- validators: `tripwire.core.validator.ALL_CHECKS`
- tripwires: `tripwire.core.session_check._TRIPWIRES` (strict pre-spawn
  checks) plus a small static list for the system-level tripwires that
  don't live in code yet (`self-review`, `pm-response-coverage`).

Lifecycle stations come from `project.config.statuses` if set, otherwise
from `DEFAULT_LIFECYCLE_STATIONS` below — matching the canonical set in
the spec example.

PM-mode redaction lives at the entry point: `build_workflow(...,
is_pm_role=True)` returns the unredacted prompt body inside each
tripwire's `prompt_revealed` field; otherwise that field is `None`.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, TypedDict

from tripwire.core import session_check, validator
from tripwire.core.store import ProjectNotFoundError, load_project
from tripwire.ui.services.role_gate import (
    PROMPT_REDACTED_PLACEHOLDER,
    redact_tripwire_prompt,
)


class StationDef(TypedDict):
    id: str
    label: str
    desc: str


# Default lifecycle if the project's `statuses` is empty. Mirrors the
# spec example. ``n`` is computed at build time so a custom `statuses`
# list automatically renumbers.
DEFAULT_LIFECYCLE_STATIONS: list[StationDef] = [
    {"id": "planned", "label": "planned", "desc": "PM has framed it, not yet spawned"},
    {"id": "queued", "label": "queued", "desc": "spawned, awaiting agent"},
    {"id": "executing", "label": "executing", "desc": "agent working"},
    {
        "id": "in_review",
        "label": "in review",
        "desc": "validators ran, awaiting human OK",
    },
    {
        "id": "verified",
        "label": "verified",
        "desc": "human or auto-validator approved",
    },
    {"id": "completed", "label": "completed", "desc": "PR merged, session signed"},
]


# Static catalogue of system-level tripwires. Each entry's `prompt` is the
# canonical instruction the tripwire would surface when fired; PM-mode
# unhides it. New tripwires authored as session_check functions are
# enumerated dynamically and don't need to be added here.
_SYSTEM_TRIPWIRES: list[dict[str, Any]] = [
    {
        "id": "self-review",
        "name": "self-review",
        "fires_on_event": "session.complete",
        "fires_on_station": "in_review",
        "blocks": True,
        "prompt": (
            "Before declaring the session complete, walk every acceptance "
            "criterion against the actual diff. Downgrade soft yeses. List "
            "every unilateral decision and skipped workflow step."
        ),
    },
    {
        "id": "pm-response-coverage",
        "name": "PM response covers self-review",
        "fires_on_event": "session.complete",
        "fires_on_station": "in_review",
        "blocks": True,
        "prompt": (
            "PM response must enumerate every self-review finding with an "
            "explicit accept / reject / followup. Silent dismissal is what "
            "this tripwire fires on."
        ),
    },
]


# Canonical lifecycle artifacts surfaced to the Workflow Map. Static for
# now; future iterations can derive these from the artifact manifest.
_LIFECYCLE_ARTIFACTS: list[dict[str, Any]] = [
    {
        "id": "a_plan",
        "label": "plan.md",
        "produced_by": "queued",
        "consumed_by": "executing",
    },
    {
        "id": "a_diff",
        "label": "staged diff",
        "produced_by": "executing",
        "consumed_by": "in_review",
    },
    {
        "id": "a_pr",
        "label": "pull request",
        "produced_by": "in_review",
        "consumed_by": "verified",
    },
    {
        "id": "a_review",
        "label": "review notes",
        "produced_by": "in_review",
        "consumed_by": "completed",
    },
    {
        "id": "a_session_sig",
        "label": "session signature",
        "produced_by": "completed",
        "consumed_by": None,
    },
]


_CONNECTORS: dict[str, list[dict[str, Any]]] = {
    "sources": [
        {
            "id": "linear",
            "name": "Linear",
            "wired_to_station": "planned",
            "data": "issues",
        },
        {
            "id": "github",
            "name": "GitHub",
            "wired_to_station": "planned",
            "data": "PRs, statuses",
        },
    ],
    "sinks": [
        {
            "id": "github_pr",
            "name": "PR open",
            "wired_from_station": "in_review",
        },
        {
            "id": "slack_ping",
            "name": "Slack ping",
            "wired_from_station": "verified",
        },
        {
            "id": "audit_log",
            "name": "Audit log",
            "wired_from_station": "completed",
        },
    ],
}


def build_workflow(
    project_dir: Path,
    *,
    project_id: str,
    is_pm_role: bool,
) -> dict[str, Any]:
    """Build the full `/api/workflow` response for *project_dir*.

    `is_pm_role` controls whether tripwire prompts are revealed. The
    `project_id` is echoed back into the payload so frontends can
    correlate without a second round trip.
    """
    stations = _build_stations(project_dir)
    return {
        "project_id": project_id,
        "lifecycle": {"stations": stations},
        "validators": _build_validators(),
        "tripwires": _build_tripwires(is_pm_role=is_pm_role),
        "connectors": _CONNECTORS,
        "artifacts": _LIFECYCLE_ARTIFACTS,
    }


def _build_stations(project_dir: Path) -> list[dict[str, Any]]:
    """Project-defined statuses if present, else `DEFAULT_LIFECYCLE_STATIONS`."""
    try:
        config = load_project(project_dir)
    except ProjectNotFoundError:
        config = None

    if config is not None and config.statuses:
        out: list[dict[str, Any]] = []
        for n, status in enumerate(config.statuses, start=1):
            out.append(
                {
                    "id": status,
                    "n": n,
                    "label": status.replace("_", " "),
                    "desc": "",
                }
            )
        return out

    return [
        {
            "id": s["id"],
            "n": n,
            "label": s["label"],
            "desc": s["desc"],
        }
        for n, s in enumerate(DEFAULT_LIFECYCLE_STATIONS, start=1)
    ]


def _build_validators() -> list[dict[str, Any]]:
    """Enumerate `validator.ALL_CHECKS` into the `/api/workflow` shape.

    The id is derived from the function name (`check_uuid_present` →
    `v_uuid_present`). The first paragraph of the docstring is the
    `checks` description; missing docstrings produce an empty string.
    Every validator fires at the `in_review` station unless future code
    adds station hints to individual checks.
    """
    out: list[dict[str, Any]] = []
    for fn in validator.ALL_CHECKS:
        name = fn.__name__
        slug = name.removeprefix("check_")
        out.append(
            {
                "id": f"v_{slug}",
                "kind": "gate",
                "name": slug.replace("_", " "),
                "checks": _first_paragraph(inspect.getdoc(fn) or ""),
                "fires_on_station": "in_review",
                "wired_to": [],
            }
        )
    return out


def _build_tripwires(*, is_pm_role: bool) -> list[dict[str, Any]]:
    """Strict-spawn tripwires + system tripwires, prompts redacted as needed."""
    out: list[dict[str, Any]] = []
    for fn in session_check._TRIPWIRES:
        slug = fn.__name__.removeprefix("_check_")
        prompt_body = _first_paragraph(inspect.getdoc(fn) or "") or (
            f"Strict pre-spawn check `{slug}` must pass before the session "
            f"is allowed to spawn."
        )
        revealed, redacted = redact_tripwire_prompt(
            prompt=prompt_body, is_pm_role=is_pm_role
        )
        out.append(
            {
                "id": f"tw_strict_{slug}",
                "kind": "tripwire",
                "name": slug.replace("_", " "),
                "fires_on_event": "session.spawn",
                "blocks": True,
                "fires_on_station": "queued",
                "prompt_revealed": revealed,
                "prompt_redacted": redacted or PROMPT_REDACTED_PLACEHOLDER,
            }
        )

    for tw in _SYSTEM_TRIPWIRES:
        revealed, redacted = redact_tripwire_prompt(
            prompt=tw["prompt"], is_pm_role=is_pm_role
        )
        out.append(
            {
                "id": tw["id"],
                "kind": "tripwire",
                "name": tw["name"],
                "fires_on_event": tw["fires_on_event"],
                "blocks": tw["blocks"],
                "fires_on_station": tw["fires_on_station"],
                "prompt_revealed": revealed,
                "prompt_redacted": redacted or PROMPT_REDACTED_PLACEHOLDER,
            }
        )
    return out


def _first_paragraph(text: str) -> str:
    """Return the first non-empty paragraph of *text* (newline-separated)."""
    text = text.strip()
    if not text:
        return ""
    return text.split("\n\n", 1)[0].strip().replace("\n", " ")


__all__ = [
    "DEFAULT_LIFECYCLE_STATIONS",
    "build_workflow",
]
