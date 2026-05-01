"""Tests for `/api/projects/{project_id}/issues` routes (KUI-27)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.ui.routes.conftest import make_project
from tripwire.ui.server import create_app
from tripwire.ui.services import project_service as _project_svc


@pytest.fixture
def rich_project(tmp_path: Path) -> Path:
    """Project with status_transitions + label_categories configured."""
    return make_project(
        tmp_path / "proj",
        extra={
            "statuses": ["todo", "in_progress", "in_review", "done"],
            "status_transitions": {
                "todo": ["in_progress"],
                "in_progress": ["in_review", "todo"],
                "in_review": ["done", "in_progress"],
                "done": [],
            },
            "label_categories": {
                "executor": [],
                "verifier": [],
                "domain": ["domain/backend", "domain/frontend"],
                "agent": [],
            },
        },
    )


@pytest.fixture
def rich_project_id(rich_project: Path) -> str:
    return _project_svc._project_id(rich_project.resolve())


@pytest.fixture
def client_with_rich(rich_project: Path, save_test_issue) -> TestClient:
    _project_svc.seed_project_index([rich_project])
    summary = _project_svc._try_load_summary(rich_project.resolve())
    if summary is not None:
        _project_svc._discovery_cache = (time.monotonic(), [summary])
    # Seed two issues.
    save_test_issue(
        rich_project,
        "KUI-1",
        status="queued",
        priority="high",
        labels=["domain/backend"],
        executor="ai",
    )
    save_test_issue(
        rich_project,
        "KUI-2",
        status="executing",
        priority="medium",
        labels=["domain/frontend"],
        executor="human",
        parent="KUI-1",
    )
    return TestClient(create_app(dev_mode=True))


class TestListIssues:
    def test_returns_all(self, client_with_rich, rich_project_id):
        r = client_with_rich.get(f"/api/projects/{rich_project_id}/issues")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 2
        keys = sorted(i["id"] for i in body)
        assert keys == ["KUI-1", "KUI-2"]

    def test_filter_by_status(self, client_with_rich, rich_project_id):
        r = client_with_rich.get(
            f"/api/projects/{rich_project_id}/issues",
            params={"status": "todo"},
        )
        assert r.status_code == 200
        body = r.json()
        assert [i["id"] for i in body] == ["KUI-1"]

    def test_filter_by_executor(self, client_with_rich, rich_project_id):
        r = client_with_rich.get(
            f"/api/projects/{rich_project_id}/issues",
            params={"executor": "human"},
        )
        assert [i["id"] for i in r.json()] == ["KUI-2"]

    def test_filter_by_label(self, client_with_rich, rich_project_id):
        r = client_with_rich.get(
            f"/api/projects/{rich_project_id}/issues",
            params={"label": "domain/backend"},
        )
        assert [i["id"] for i in r.json()] == ["KUI-1"]

    def test_filter_by_parent(self, client_with_rich, rich_project_id):
        r = client_with_rich.get(
            f"/api/projects/{rich_project_id}/issues",
            params={"parent": "KUI-1"},
        )
        assert [i["id"] for i in r.json()] == ["KUI-2"]

    def test_no_filter_returns_full_list(self, client_with_rich, rich_project_id):
        r = client_with_rich.get(f"/api/projects/{rich_project_id}/issues")
        assert len(r.json()) == 2


class TestGetIssue:
    def test_happy_path(self, client_with_rich, rich_project_id):
        r = client_with_rich.get(f"/api/projects/{rich_project_id}/issues/KUI-1")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "KUI-1"
        assert body["status"] == "queued"
        assert "body" in body  # detail includes body
        assert "refs" in body

    def test_unknown_key_returns_404(self, client_with_rich, rich_project_id):
        r = client_with_rich.get(f"/api/projects/{rich_project_id}/issues/KUI-999")
        assert r.status_code == 404
        body = r.json()
        assert body["code"] == "issue/not_found"
        assert "KUI-999" in body["detail"]

    def test_malformed_key_returns_400(self, client_with_rich, rich_project_id):
        r = client_with_rich.get(f"/api/projects/{rich_project_id}/issues/not-a-key")
        assert r.status_code == 400
        body = r.json()
        assert body["code"] == "issue/bad_key"

    def test_wrong_prefix_returns_400(self, client_with_rich, rich_project_id):
        # Wrong prefix (OTHER-1 vs expected KUI-1) — 400, not 404.
        r = client_with_rich.get(f"/api/projects/{rich_project_id}/issues/OTHER-1")
        assert r.status_code == 400
        assert r.json()["code"] == "issue/bad_key"


class TestPatchIssue:
    def test_valid_transition(self, client_with_rich, rich_project_id, tmp_path):
        import os

        os.environ["TRIPWIRE_LOG_DIR"] = str(tmp_path / "audit-logs")
        r = client_with_rich.patch(
            f"/api/projects/{rich_project_id}/issues/KUI-1",
            json={"status": "in_progress"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "executing"

    def test_invalid_transition_returns_409(
        self,
        client_with_rich,
        rich_project_id,
        tmp_path,
    ):
        import os

        os.environ["TRIPWIRE_LOG_DIR"] = str(tmp_path / "audit-logs")
        # `todo -> done` is not in the allowed transitions map.
        r = client_with_rich.patch(
            f"/api/projects/{rich_project_id}/issues/KUI-1",
            json={"status": "done"},
        )
        assert r.status_code == 409
        body = r.json()
        assert body["code"] == "issue/invalid_transition"
        assert "todo" in body["detail"] and "done" in body["detail"]

    def test_unknown_key_returns_404(self, client_with_rich, rich_project_id):
        r = client_with_rich.patch(
            f"/api/projects/{rich_project_id}/issues/KUI-999",
            json={"status": "in_progress"},
        )
        assert r.status_code == 404
        assert r.json()["code"] == "issue/not_found"

    def test_malformed_key_returns_400(self, client_with_rich, rich_project_id):
        r = client_with_rich.patch(
            f"/api/projects/{rich_project_id}/issues/nope",
            json={"status": "in_progress"},
        )
        assert r.status_code == 400

    def test_empty_patch_is_noop_200(
        self,
        client_with_rich,
        rich_project_id,
        tmp_path,
    ):
        import os

        os.environ["TRIPWIRE_LOG_DIR"] = str(tmp_path / "audit-logs")
        r = client_with_rich.patch(
            f"/api/projects/{rich_project_id}/issues/KUI-1",
            json={},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "queued"

    def test_extra_field_returns_422(self, client_with_rich, rich_project_id):
        r = client_with_rich.patch(
            f"/api/projects/{rich_project_id}/issues/KUI-1",
            json={"title": "cannot set this"},
        )
        # IssuePatch has extra="forbid".
        assert r.status_code == 422


class TestValidateIssue:
    def test_returns_validation_report(
        self,
        client_with_rich,
        rich_project_id,
    ):
        r = client_with_rich.post(
            f"/api/projects/{rich_project_id}/issues/KUI-1/validate"
        )
        # Body always 200 regardless of error count.
        assert r.status_code == 200
        body = r.json()
        assert "summary" in body
        assert "errors" in body
        assert "warnings" in body
        assert isinstance(body["errors"], list)

    def test_unknown_key_returns_404(
        self,
        client_with_rich,
        rich_project_id,
    ):
        r = client_with_rich.post(
            f"/api/projects/{rich_project_id}/issues/KUI-999/validate"
        )
        assert r.status_code == 404
        assert r.json()["code"] == "issue/not_found"


class TestOpenAPI:
    def test_schema_registers_endpoints(self, client_with_rich):
        schema = client_with_rich.get("/openapi.json").json()
        paths = schema["paths"]
        assert "/api/projects/{project_id}/issues" in paths
        assert "/api/projects/{project_id}/issues/{key}" in paths
        assert "/api/projects/{project_id}/issues/{key}/validate" in paths
