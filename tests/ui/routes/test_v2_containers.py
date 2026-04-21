"""Integration tests for the v2 containers stub router (KUI-41)."""

from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient

from tripwire.ui.routes._v2_stub import V2_NOT_IMPLEMENTED_CODE
from tripwire.ui.server import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(dev_mode=True))


def _assert_v2_envelope(resp) -> None:
    assert resp.status_code == 501, f"expected 501, got {resp.status_code}"
    body = resp.json()
    assert "detail" in body, body
    detail = body["detail"]
    assert isinstance(detail, dict), detail
    assert detail["code"] == V2_NOT_IMPLEMENTED_CODE
    assert isinstance(detail.get("detail"), str) and detail["detail"]
    assert isinstance(detail.get("extras"), dict)


class TestContainerRoutes501:
    def test_list_containers(self, client):
        _assert_v2_envelope(client.get("/api/containers"))

    def test_get_stats(self, client):
        _assert_v2_envelope(client.get("/api/containers/abc123/stats"))

    def test_get_logs(self, client):
        _assert_v2_envelope(client.get("/api/containers/abc123/logs"))

    def test_launch(self, client):
        _assert_v2_envelope(
            client.post(
                "/api/containers/launch",
                json={"session_id": "s1", "project_id": "p1"},
            )
        )

    def test_stop(self, client):
        _assert_v2_envelope(client.post("/api/containers/abc123/stop"))

    def test_terminal(self, client):
        _assert_v2_envelope(client.post("/api/containers/abc123/terminal"))

    def test_cleanup(self, client):
        _assert_v2_envelope(client.post("/api/containers/cleanup"))


class TestContainerOpenAPI:
    def test_all_paths_tagged_containers_v2(self, client):
        spec = client.get("/openapi.json").json()
        paths = spec["paths"]
        expected = {
            "/api/containers": "get",
            "/api/containers/{container_id}/stats": "get",
            "/api/containers/{container_id}/logs": "get",
            "/api/containers/launch": "post",
            "/api/containers/{container_id}/stop": "post",
            "/api/containers/{container_id}/terminal": "post",
            "/api/containers/cleanup": "post",
        }
        for path, method in expected.items():
            assert path in paths, f"missing OpenAPI path {path}"
            op = paths[path][method]
            assert "containers (v2)" in op.get("tags", []), (
                f"{path}.{method} missing containers (v2) tag"
            )


class TestNoDockerImport:
    def test_docker_not_imported(self):
        from tripwire.ui.routes import containers  # noqa: F401
        from tripwire.ui.services import container_service  # noqa: F401

        assert "docker" not in sys.modules, (
            f"stub imported docker: {sys.modules.get('docker')!r}"
        )
