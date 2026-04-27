"""Tests for `/api/projects/{project_id}/inbox` routes (phase D)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.ui.routes.conftest import make_project
from tripwire.core import paths
from tripwire.ui.server import create_app
from tripwire.ui.services import project_service as _project_svc


def _write_entry(
    project_dir: Path,
    entry_id: str,
    *,
    bucket: str = "blocked",
    title: str = "test entry",
    resolved: bool = False,
    created_at: str = "2026-04-27T10:00:00Z",
) -> None:
    inbox = paths.inbox_dir(project_dir)
    inbox.mkdir(exist_ok=True)
    text = (
        "---\n"
        f"id: {entry_id}\n"
        "uuid: 12345678-1234-4123-8123-123456789abc\n"
        f"created_at: {created_at}\n"
        "author: pm-agent\n"
        f"bucket: {bucket}\n"
        f"title: {title}\n"
        "references: []\n"
        f"resolved: {str(resolved).lower()}\n"
        "---\n"
        "body text\n"
    )
    (inbox / f"{entry_id}.md").write_text(text, encoding="utf-8")


@pytest.fixture
def inbox_project(tmp_path: Path) -> Path:
    project = make_project(tmp_path / "proj")
    _write_entry(project, "inb-a", bucket="blocked", title="needs you")
    _write_entry(project, "inb-b", bucket="fyi", title="happened")
    _write_entry(project, "inb-c", bucket="fyi", title="resolved", resolved=True)
    return project


@pytest.fixture
def inbox_project_id(inbox_project: Path) -> str:
    return _project_svc._project_id(inbox_project.resolve())


@pytest.fixture
def inbox_client(inbox_project: Path) -> TestClient:
    _project_svc.seed_project_index([inbox_project])
    summary = _project_svc._try_load_summary(inbox_project.resolve())
    if summary is not None:
        _project_svc._discovery_cache = (time.monotonic(), [summary])
    return TestClient(create_app(dev_mode=True))


class TestListInboxRoute:
    def test_returns_all_entries(self, inbox_client, inbox_project_id):
        r = inbox_client.get(f"/api/projects/{inbox_project_id}/inbox")
        assert r.status_code == 200
        ids = sorted(item["id"] for item in r.json())
        assert ids == ["inb-a", "inb-b", "inb-c"]

    def test_filter_by_bucket(self, inbox_client, inbox_project_id):
        r = inbox_client.get(
            f"/api/projects/{inbox_project_id}/inbox", params={"bucket": "blocked"}
        )
        assert r.status_code == 200
        assert [i["id"] for i in r.json()] == ["inb-a"]

    def test_filter_by_resolved(self, inbox_client, inbox_project_id):
        r = inbox_client.get(
            f"/api/projects/{inbox_project_id}/inbox", params={"resolved": "false"}
        )
        ids = sorted(i["id"] for i in r.json())
        assert ids == ["inb-a", "inb-b"]


class TestGetInboxRoute:
    def test_returns_entry(self, inbox_client, inbox_project_id):
        r = inbox_client.get(f"/api/projects/{inbox_project_id}/inbox/inb-a")
        assert r.status_code == 200
        assert r.json()["title"] == "needs you"

    def test_404_when_missing(self, inbox_client, inbox_project_id):
        r = inbox_client.get(f"/api/projects/{inbox_project_id}/inbox/inb-nope")
        assert r.status_code == 404
        assert r.json()["code"] == "inbox/not_found"


class TestResolveInboxRoute:
    def test_resolves_entry(self, inbox_client, inbox_project_id):
        r = inbox_client.post(
            f"/api/projects/{inbox_project_id}/inbox/inb-a/resolve",
            json={"resolved_by": "alice"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["resolved"] is True
        assert body["resolved_by"] == "alice"

    def test_resolve_without_body(self, inbox_client, inbox_project_id):
        # POST with no body should still succeed — defaults to "ui-user".
        r = inbox_client.post(f"/api/projects/{inbox_project_id}/inbox/inb-a/resolve")
        assert r.status_code == 200
        assert r.json()["resolved_by"] == "ui-user"

    def test_404_on_missing_entry(self, inbox_client, inbox_project_id):
        r = inbox_client.post(
            f"/api/projects/{inbox_project_id}/inbox/inb-nope/resolve", json={}
        )
        assert r.status_code == 404
