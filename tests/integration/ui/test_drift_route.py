"""Integration tests for the drift report route (KUI-157 / I4).

Exercises ``GET /api/projects/{project_id}/drift``: returns
``{score, breakdown, workflow_drift_events}``.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from tripwire.ui.dependencies import reset_project_cache
from tripwire.ui.server import create_app
from tripwire.ui.services import project_service as _project_svc


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "Drift Fixture",
                "key_prefix": "DR",
                "phase": "executing",
                "next_issue_number": 1,
                "next_session_number": 1,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    for sub in ("issues", "nodes", "sessions"):
        (project / sub).mkdir(exist_ok=True)
    return project


@pytest.fixture
def client(project_dir: Path) -> TestClient:
    _project_svc.reload_project_index()
    reset_project_cache()
    _project_svc.seed_project_index([project_dir])
    summary = _project_svc._try_load_summary(project_dir.resolve())
    if summary is not None:
        _project_svc._discovery_cache = (time.monotonic(), [summary])
    yield TestClient(create_app(dev_mode=True))
    _project_svc.reload_project_index()
    reset_project_cache()


@pytest.fixture
def project_id(project_dir: Path) -> str:
    return _project_svc._project_id(project_dir.resolve())


def test_drift_route_returns_score_and_breakdown(
    client: TestClient, project_id: str
) -> None:
    resp = client.get(f"/api/projects/{project_id}/drift")
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "score" in payload
    assert isinstance(payload["score"], int)
    assert 0 <= payload["score"] <= 100
    breakdown = payload["breakdown"]
    assert {
        "stale_pins",
        "unresolved_refs",
        "stale_concepts",
        "workflow_drift_events",
    }.issubset(breakdown.keys())


def test_drift_route_clean_project_returns_full_score(
    client: TestClient, project_id: str
) -> None:
    """Empty project (no issues, no nodes, no events log) → score 100."""
    resp = client.get(f"/api/projects/{project_id}/drift")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["score"] == 100
    assert payload["workflow_drift_events"] == []


def test_drift_route_includes_recent_workflow_drift_events(
    client: TestClient, project_id: str, project_dir: Path
) -> None:
    """Recent workflow_drift events are surfaced for the drill-down."""
    events_log = project_dir / ".tripwire" / "events.log"
    events_log.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(tz=timezone.utc).isoformat()
    events_log.write_text(
        yaml.safe_dump(
            {"event": "workflow_drift", "at": now, "kind": "missing_artifact"},
            default_flow_style=True,
        ).strip()
        + "\n"
        + yaml.safe_dump(
            {"event": "workflow_drift", "at": now, "kind": "stale_pin"},
            default_flow_style=True,
        ).strip()
        + "\n"
        + yaml.safe_dump(
            {"event": "other", "at": now, "kind": "noise"},
            default_flow_style=True,
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    resp = client.get(f"/api/projects/{project_id}/drift")
    assert resp.status_code == 200
    payload = resp.json()
    drift_events = payload["workflow_drift_events"]
    assert len(drift_events) == 2
    # Newest first ordering — same timestamp here, but the filter
    # only includes the workflow_drift kind.
    kinds = {ev["kind"] for ev in drift_events}
    assert kinds == {"missing_artifact", "stale_pin"}
