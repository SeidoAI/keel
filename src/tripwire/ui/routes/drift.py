"""Drift report route — KUI-157 / I4.

Single endpoint:

    GET  /api/projects/{project_id}/drift

Returns the unified coherence score plus per-signal breakdown for the
Drift Report UI screen. Wraps the existing
``tripwire.core.drift.compute_coherence`` substrate (shipped in
v09-entity-graph-substrate).

Workflow-drift events are also surfaced as a chronological list (last
30 days, capped at 100 entries) so the UI can render the per-event
drill-down without a second request.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends

from tripwire.core.drift import compute_coherence
from tripwire.ui.dependencies import ProjectContext, get_project

router = APIRouter(prefix="/api/projects/{project_id}", tags=["drift"])

_EVENTS_LOG_REL = ".tripwire/events.log"
_DRILL_DOWN_DAYS = 30
_DRILL_DOWN_CAP = 100


@router.get("/drift")
async def get_drift_route(
    project: ProjectContext = Depends(get_project),  # noqa: B008
) -> dict[str, Any]:
    """Return ``{score, breakdown, workflow_drift_events}``."""
    report = compute_coherence(project.project_dir)
    events = _recent_workflow_drift_events(project.project_dir)
    return {
        "score": report.score,
        "breakdown": report.breakdown,
        "workflow_drift_events": events,
    }


def _recent_workflow_drift_events(project_dir: Path) -> list[dict[str, Any]]:
    """Return up to ``_DRILL_DOWN_CAP`` recent workflow_drift events.

    Reads ``.tripwire/events.log`` (the substrate shipped in
    v09-workflow-substrate). Each event is one YAML record per line.
    Returns at most ``_DRILL_DOWN_CAP`` entries from the most recent
    ``_DRILL_DOWN_DAYS`` days, sorted newest-first.
    """
    log_path = project_dir / _EVENTS_LOG_REL
    if not log_path.is_file():
        return []

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=_DRILL_DOWN_DAYS)

    out: list[tuple[datetime, dict[str, Any]]] = []
    try:
        with log_path.open(encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    record: Any = yaml.safe_load(line)
                except yaml.YAMLError:
                    continue
                if not isinstance(record, dict):
                    continue
                if record.get("event") != "workflow_drift":
                    continue
                ts = record.get("at")
                if not isinstance(ts, str):
                    continue
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
                out.append((dt, record))
    except OSError:
        return []

    out.sort(key=lambda pair: pair[0], reverse=True)
    return [record for _, record in out[:_DRILL_DOWN_CAP]]
