"""Build the `/api/workflow` graph by introspecting registries.

The Workflow Map UI consumes this — see
`docs/specs/2026-04-26-v08-handoff.md` §2.1 for the response shape and
the layout-hint contract (no absolute coordinates; each entity carries
the station it attaches to so the UI can lay it out).

The `validators` and `jit_prompts` lists are derived from real registries:
- validators: `tripwire.core.validator.ALL_CHECKS`
- jit_prompts: the system JIT prompts surfaced to agents at lifecycle
  events. Detector-style validation tripwires stay out of this prompt lane.

Lifecycle stations come from `project.config.statuses` if set, otherwise
from `DEFAULT_LIFECYCLE_STATIONS` below — matching the canonical set in
the spec example.

PM-mode redaction lives at the entry point: `build_workflow(...,
is_pm_role=True)` returns the unredacted prompt body inside each JIT
prompt's `prompt_revealed` field; otherwise that field is `None`.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, TypedDict

from tripwire.core import validator
from tripwire.core.store import ProjectNotFoundError, load_project
from tripwire.ui.services.role_gate import (
    PROMPT_REDACTED_PLACEHOLDER,
    redact_jit_prompt,
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


# Static catalogue of system-level JIT prompts. Each entry's `prompt` is the
# canonical instruction the prompt would surface when fired; PM-mode unhides it.
_SYSTEM_JIT_PROMPTS: list[dict[str, Any]] = [
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
            "this JIT prompt fires on."
        ),
    },
    {
        "id": "phase-transition",
        "name": "phase advanced past open prev-phase issues",
        "fires_on_event": "session.complete",
        "fires_on_station": "verified",
        "blocks": True,
        "prompt": (
            "The project's phase has been advanced but issues labelled "
            "with the previous phase are still open. Either close the "
            "issues, roll the phase back, or re-tag the issues with "
            "the current phase."
        ),
    },
    {
        "id": "followups-not-filed",
        "name": "deferred follow-ups must be filed as issues",
        "fires_on_event": "session.complete",
        "fires_on_station": "verified",
        "blocks": True,
        "prompt": (
            "PM-response declared deferred items with follow_up keys, "
            "but the referenced issues aren't on disk. Follow-ups are "
            "immediate, not deferred — file the issue or convert the "
            "deferral."
        ),
    },
    {
        "id": "stopped-to-ask",
        "name": "stop-and-ask boundary crossed silently",
        "fires_on_event": "session.complete",
        "fires_on_station": "verified",
        "blocks": True,
        "prompt": (
            "The session plan declared a Stop-and-ask section, the diff "
            "touched files outside session.yaml.key_files, and no "
            "stop-and-ask comment surfaced the call. Re-scope or revert "
            "the out-of-scope work."
        ),
    },
    {
        "id": "write-count",
        "name": "validation cadence — write count over threshold",
        "fires_on_event": "session.complete",
        "fires_on_station": "verified",
        "blocks": True,
        "prompt": (
            "File-edit tool calls in this session crossed the configured "
            "threshold without an intervening `tripwire validate` run. "
            "Run validate now and walk the findings."
        ),
    },
    {
        "id": "cost-ceiling",
        "name": "cumulative session cost over ceiling",
        "fires_on_event": "session.complete",
        "fires_on_station": "verified",
        "blocks": True,
        "prompt": (
            "The session's cumulative cost has crossed the configured "
            "ceiling. Either justify and recalibrate the ceiling, or "
            "diagnose the runaway and propose a guardrail."
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

    `is_pm_role` controls whether JIT prompt bodies are revealed. The
    `project_id` is echoed back into the payload so frontends can
    correlate without a second round trip.

    The response shape carries two views:

    - **legacy** (``lifecycle``, ``validators``, ``jit_prompts``,
      ``connectors``, ``artifacts``) — the introspection-derived
      shape from v0.8 the existing Workflow Map UI consumes.
    - **workflows** (KUI-125) — the parsed workflow.yaml tree, one
      entry per declared workflow. Carries stations with their
      ``next:`` shape (single / conditional / terminal) and the
      validators/JIT prompts/prompt-checks each station references.
      The Workflow Map renders this directly so a project can
      define new workflows (pm-review, future inbox-handling,
      issue-lifecycle) without extending the backend.
    """
    stations = _build_stations(project_dir)
    return {
        "project_id": project_id,
        "lifecycle": {"stations": stations},
        "validators": _build_validators(),
        "jit_prompts": _build_jit_prompts(is_pm_role=is_pm_role),
        "connectors": _CONNECTORS,
        "artifacts": _LIFECYCLE_ARTIFACTS,
        "workflows": _build_workflows(project_dir),
    }


def _build_workflows(project_dir: Path) -> list[dict[str, Any]]:
    """Surface the parsed ``workflow.yaml`` for the Workflow Map UI.

    Each entry is one workflow declared in the file. ``next:`` is
    serialized as a discriminated union mirroring
    :class:`tripwire.core.workflow.schema.NextSpec`. Empty list when
    the file is missing or parses to zero workflows.
    """
    from tripwire.core.workflow.loader import load_workflows
    from tripwire.core.workflow.schema import NextSpec

    spec = load_workflows(project_dir)
    out: list[dict[str, Any]] = []
    for wf_id, wf in spec.workflows.items():
        stations: list[dict[str, Any]] = []
        for station in wf.stations:
            stations.append(
                {
                    "id": station.id,
                    "next": _next_spec_to_dict(station.next),
                    "validators": list(station.validators),
                    "jit_prompts": list(station.jit_prompts),
                    "prompt_checks": list(station.prompt_checks),
                }
            )
        out.append(
            {
                "id": wf_id,
                "actor": wf.actor,
                "trigger": wf.trigger,
                "stations": stations,
            }
        )
    # `NextSpec` import was just for the helper below; keep the
    # serialiser local so the route module doesn't import core.workflow
    # directly.
    _ = NextSpec  # silence unused-import for mypy-strict linters
    return out


def _next_spec_to_dict(next_spec: Any) -> dict[str, Any]:
    """Serialize a :class:`NextSpec` into a plain dict.

    Shape:
        {"kind": "single", "single": "<id>"}
        {"kind": "conditional", "branches":
            [{"if": "<predicate>", "then": "<id>"} | {"else": "<id>"}]}
        {"kind": "terminal"}
    """
    kind = next_spec.kind
    if kind == "single":
        return {"kind": "single", "single": next_spec.single}
    if kind == "conditional":
        branches: list[dict[str, Any]] = []
        for branch in next_spec.conditional or []:
            if branch.predicate is None:
                branches.append({"else": branch.then})
            else:
                pred = branch.predicate
                branches.append(
                    {"if": f"{pred.field} {pred.op} {pred.value}", "then": branch.then}
                )
        return {"kind": "conditional", "branches": branches}
    return {"kind": "terminal"}


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


def _build_jit_prompts(*, is_pm_role: bool) -> list[dict[str, Any]]:
    """System JIT prompts with prompt bodies redacted as needed."""
    out: list[dict[str, Any]] = []
    for prompt in _SYSTEM_JIT_PROMPTS:
        revealed, redacted = redact_jit_prompt(
            prompt=prompt["prompt"], is_pm_role=is_pm_role
        )
        out.append(
            {
                "id": prompt["id"],
                "kind": "jit_prompt",
                "name": prompt["name"],
                "fires_on_event": prompt["fires_on_event"],
                "blocks": prompt["blocks"],
                "fires_on_station": prompt["fires_on_station"],
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
