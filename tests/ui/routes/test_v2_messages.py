"""Integration tests for the v2 messages stub router (KUI-42)."""

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


class TestMessageRoutes501:
    def test_create(self, client):
        _assert_v2_envelope(
            client.post(
                "/api/messages",
                json={
                    "session_id": "s1",
                    "type": "question",
                    "priority": "normal",
                    "body": "hi",
                },
            )
        )

    def test_list(self, client):
        _assert_v2_envelope(client.get("/api/messages", params={"session_id": "s1"}))

    def test_pending(self, client):
        _assert_v2_envelope(
            client.get("/api/messages/pending", params={"session_id": "s1"})
        )

    def test_respond(self, client):
        _assert_v2_envelope(
            client.post(
                "/api/messages/abc/respond",
                json={"body": "ok", "decision": "approve"},
            )
        )

    def test_unread(self, client):
        _assert_v2_envelope(client.get("/api/messages/unread"))


class TestMessagesOpenAPI:
    def test_all_paths_tagged_messages_v2(self, client):
        spec = client.get("/openapi.json").json()
        paths = spec["paths"]
        expected = {
            "/api/messages": ("post", "get"),
            "/api/messages/pending": ("get",),
            "/api/messages/{message_id}/respond": ("post",),
            "/api/messages/unread": ("get",),
        }
        for path, methods in expected.items():
            assert path in paths, f"missing OpenAPI path {path}"
            for method in methods:
                op = paths[path][method]
                assert "messages (v2)" in op.get("tags", []), (
                    f"{path}.{method} missing messages (v2) tag"
                )


class TestNoSqliteImport:
    def test_sqlite_not_imported(self):
        from tripwire.ui.routes import messages  # noqa: F401
        from tripwire.ui.services import message_service  # noqa: F401

        assert "sqlite3" not in sys.modules, (
            f"stub imported sqlite3: {sys.modules.get('sqlite3')!r}"
        )
