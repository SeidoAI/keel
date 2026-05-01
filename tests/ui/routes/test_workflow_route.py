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
    assert "jit_prompts" in body and len(body["jit_prompts"]) > 0
    assert "connectors" in body
    assert "artifacts" in body


def test_workflow_redacts_jit_prompt_for_non_pm(
    seeded_client: TestClient, project_id: str
) -> None:
    resp = seeded_client.get(f"/api/projects/{project_id}/workflow")
    assert resp.status_code == 200
    for prompt in resp.json()["jit_prompts"]:
        assert prompt["prompt_revealed"] is None


def test_workflow_reveals_jit_prompt_for_pm(
    seeded_client: TestClient, project_id: str
) -> None:
    resp = seeded_client.get(
        f"/api/projects/{project_id}/workflow",
        headers={"X-Tripwire-Role": "pm"},
    )
    assert resp.status_code == 200, resp.text
    revealed = [
        prompt["prompt_revealed"]
        for prompt in resp.json()["jit_prompts"]
        if prompt["prompt_revealed"]
    ]
    assert revealed, "expected at least one JIT prompt to expose its body"


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
        prompt["prompt_revealed"]
        for prompt in resp.json()["jit_prompts"]
        if prompt["prompt_revealed"]
    ]
    assert revealed
