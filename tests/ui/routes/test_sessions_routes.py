"""Tests for `/api/projects/{project_id}/sessions` routes (KUI-30)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.ui.routes.conftest import make_project
from tripwire.ui.server import create_app
from tripwire.ui.services import project_service as _project_svc


@pytest.fixture
def sess_project(tmp_path: Path) -> Path:
    return make_project(tmp_path / "proj")


@pytest.fixture
def sess_project_id(sess_project: Path) -> str:
    return _project_svc._project_id(sess_project.resolve())


@pytest.fixture
def empty_sessions_client(sess_project: Path) -> TestClient:
    _project_svc.seed_project_index([sess_project])
    summary = _project_svc._try_load_summary(sess_project.resolve())
    if summary is not None:
        _project_svc._discovery_cache = (time.monotonic(), [summary])
    return TestClient(create_app(dev_mode=True))


@pytest.fixture
def session_client(sess_project: Path, save_test_session) -> TestClient:
    _project_svc.seed_project_index([sess_project])
    summary = _project_svc._try_load_summary(sess_project.resolve())
    if summary is not None:
        _project_svc._discovery_cache = (time.monotonic(), [summary])
    save_test_session(sess_project, "session-a", plan=True, status="planned")
    save_test_session(
        sess_project,
        "session-b",
        plan=True,
        status="completed",
    )
    return TestClient(create_app(dev_mode=True))


class TestListSessions:
    def test_returns_all(self, session_client, sess_project_id):
        r = session_client.get(f"/api/projects/{sess_project_id}/sessions")
        assert r.status_code == 200
        ids = sorted(s["id"] for s in r.json())
        assert ids == ["session-a", "session-b"]

    def test_filter_by_status(self, session_client, sess_project_id):
        r = session_client.get(
            f"/api/projects/{sess_project_id}/sessions",
            params={"status": "planned"},
        )
        assert [s["id"] for s in r.json()] == ["session-a"]

    def test_unknown_status_returns_empty(self, session_client, sess_project_id):
        r = session_client.get(
            f"/api/projects/{sess_project_id}/sessions",
            params={"status": "imaginary"},
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_empty_project_returns_empty(
        self,
        empty_sessions_client,
        sess_project_id,
    ):
        r = empty_sessions_client.get(f"/api/projects/{sess_project_id}/sessions")
        assert r.status_code == 200
        assert r.json() == []


class TestGetSession:
    def test_happy_path(self, session_client, sess_project_id):
        r = session_client.get(f"/api/projects/{sess_project_id}/sessions/session-a")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "session-a"
        assert body["status"] == "planned"
        assert "plan_md" in body
        assert "artifact_status" in body
        assert "task_progress" in body

    def test_unknown_sid_returns_404_envelope(
        self,
        session_client,
        sess_project_id,
    ):
        r = session_client.get(
            f"/api/projects/{sess_project_id}/sessions/does-not-exist"
        )
        assert r.status_code == 404
        body = r.json()
        assert body["code"] == "session/not_found"
        assert "does-not-exist" in body["detail"]

    def test_malformed_sid_uppercase_returns_400(
        self,
        session_client,
        sess_project_id,
    ):
        r = session_client.get(f"/api/projects/{sess_project_id}/sessions/UpperCase")
        assert r.status_code == 400
        assert r.json()["code"] == "session/bad_slug"

    def test_malformed_sid_leading_digit_returns_400(
        self,
        session_client,
        sess_project_id,
    ):
        r = session_client.get(f"/api/projects/{sess_project_id}/sessions/1bad")
        assert r.status_code == 400


class TestOpenAPI:
    def test_registers_paths(self, session_client):
        schema = session_client.get("/openapi.json").json()
        paths = schema["paths"]
        assert "/api/projects/{project_id}/sessions" in paths
        assert "/api/projects/{project_id}/sessions/{sid}" in paths
