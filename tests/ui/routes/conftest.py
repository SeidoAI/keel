"""Shared fixtures + envelope helpers for route tests.

Also exposes fixtures used by v1 route tests (KUI-26..34) that need a
real on-disk fixture project seeded into the service-layer index.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tripwire.ui.dependencies import reset_project_cache
from tripwire.ui.routes._v2_stub import V2_NOT_IMPLEMENTED_CODE
from tripwire.ui.server import create_app
from tripwire.ui.services import project_service as _project_svc


@pytest.fixture
def client() -> TestClient:
    """TestClient against the full FastAPI app in dev-mode."""
    return TestClient(create_app(dev_mode=True))


def assert_v2_envelope(resp) -> None:
    """Assert *resp* is the canonical v2 501 envelope.

    The expected body shape is::

        {"detail": {"detail": <str>, "code": "v2/not_implemented",
                    "extras": <dict>}}
    """
    assert resp.status_code == 501, f"expected 501, got {resp.status_code}"
    body = resp.json()
    assert "detail" in body, body
    detail = body["detail"]
    assert isinstance(detail, dict), detail
    assert detail["code"] == V2_NOT_IMPLEMENTED_CODE
    assert isinstance(detail.get("detail"), str) and detail["detail"]
    assert isinstance(detail.get("extras"), dict)


# ---------------------------------------------------------------------------
# v1 route fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_project_state():
    """Clear project-service caches around every route test."""
    _project_svc.reload_project_index()
    reset_project_cache()
    yield
    _project_svc.reload_project_index()
    reset_project_cache()


def make_project(
    project_dir: Path,
    *,
    key_prefix: str = "KUI",
    extra: dict | None = None,
) -> Path:
    """Write a minimal valid `project.yaml` under *project_dir*.

    Optional *extra* kwargs are merged into the YAML payload so tests
    can seed `status_transitions`, `statuses`, `label_categories`, etc.
    without reimplementing the boilerplate.

    Returns the same path for convenience.
    """
    import yaml

    project_dir.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "name": "TripwireProj",
        "key_prefix": key_prefix,
        "description": "A fixture project",
        "phase": "scoping",
        "next_issue_number": 1,
        "next_session_number": 1,
    }
    if extra:
        payload.update(extra)
    (project_dir / "project.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
    )
    for sub in ("issues", "nodes", "sessions"):
        (project_dir / sub).mkdir(exist_ok=True)
    return project_dir


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Minimal fixture project on disk with enums/, orchestration/, etc."""
    return make_project(tmp_path / "proj")


@pytest.fixture
def project_id(project_dir: Path) -> str:
    """Stable 12-hex id for *project_dir* matching server-side derivation."""
    return _project_svc._project_id(project_dir.resolve())


@pytest.fixture
def seeded_client(project_dir: Path) -> TestClient:
    """TestClient with *project_dir* registered in the service index.

    Also pre-populates the 60s discovery cache so `GET /api/projects`
    finds the fixture without touching the real filesystem.
    """
    _project_svc.seed_project_index([project_dir])
    summary = _project_svc._try_load_summary(project_dir.resolve())
    if summary is not None:
        _project_svc._discovery_cache = (time.monotonic(), [summary])
    return TestClient(create_app(dev_mode=True))
