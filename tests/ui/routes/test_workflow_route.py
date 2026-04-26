"""Tests for `GET /api/projects/{pid}/workflow`.

KUI-100 — see `docs/specs/2026-04-26-v08-handoff.md` §2.1, §2.5.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_workflow_returns_full_graph(
    seeded_client: TestClient, project_id: str
) -> None:
    resp = seeded_client.get(f"/api/projects/{project_id}/workflow")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["project_id"] == project_id
    assert "lifecycle" in body
    assert "validators" in body and len(body["validators"]) > 0
    assert "tripwires" in body and len(body["tripwires"]) > 0
    assert "connectors" in body
    assert "artifacts" in body


def test_workflow_redacts_tripwire_prompt_for_non_pm(
    seeded_client: TestClient, project_id: str
) -> None:
    resp = seeded_client.get(f"/api/projects/{project_id}/workflow")
    assert resp.status_code == 200
    for tw in resp.json()["tripwires"]:
        assert tw["prompt_revealed"] is None


def test_workflow_reveals_tripwire_prompt_for_pm(
    seeded_client: TestClient, project_id: str
) -> None:
    resp = seeded_client.get(
        f"/api/projects/{project_id}/workflow",
        headers={"X-Tripwire-Role": "pm"},
    )
    assert resp.status_code == 200, resp.text
    revealed = [
        tw["prompt_revealed"]
        for tw in resp.json()["tripwires"]
        if tw["prompt_revealed"]
    ]
    assert revealed, "expected at least one tripwire to expose its prompt"


def test_workflow_unknown_project_returns_404(client: TestClient) -> None:
    resp = client.get("/api/projects/000000000000/workflow")
    assert resp.status_code == 404, resp.text


def test_workflow_pm_header_case_insensitive(
    seeded_client: TestClient, project_id: str
) -> None:
    resp = seeded_client.get(
        f"/api/projects/{project_id}/workflow",
        headers={"x-tripwire-role": "PM"},
    )
    assert resp.status_code == 200
    revealed = [
        tw["prompt_revealed"]
        for tw in resp.json()["tripwires"]
        if tw["prompt_revealed"]
    ]
    assert revealed
