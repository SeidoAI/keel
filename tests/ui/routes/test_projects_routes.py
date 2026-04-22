"""Tests for `/api/projects` routes (KUI-26)."""

from __future__ import annotations


class TestListProjects:
    def test_returns_array_with_fixture(self, seeded_client, project_id):
        r = seeded_client.get("/api/projects")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        ids = [p["id"] for p in body]
        assert project_id in ids

    def test_fixture_summary_shape(self, seeded_client, project_id):
        r = seeded_client.get("/api/projects")
        assert r.status_code == 200
        entry = next(p for p in r.json() if p["id"] == project_id)
        assert entry["name"] == "TripwireProj"
        assert entry["key_prefix"] == "KUI"
        assert entry["issue_count"] == 0
        assert entry["session_count"] == 0


class TestGetProject:
    def test_happy_path(self, seeded_client, project_id):
        r = seeded_client.get(f"/api/projects/{project_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == project_id
        assert body["name"] == "TripwireProj"
        assert body["key_prefix"] == "KUI"
        assert body["phase"] == "scoping"
        assert body["description"] == "A fixture project"

    def test_unknown_project_returns_404_envelope(self, seeded_client):
        r = seeded_client.get("/api/projects/deadbeef1234")
        assert r.status_code == 404
        body = r.json()
        assert body["detail"].startswith("Project")
        assert body["code"] == "project/not_found"

    def test_malformed_project_id_returns_422(self, seeded_client):
        # path pattern `^[a-f0-9]{12}$` rejects non-hex / wrong length.
        r = seeded_client.get("/api/projects/NOTHEX")
        assert r.status_code == 422


class TestOpenAPI:
    def test_schema_registers_endpoints(self, seeded_client):
        schema = seeded_client.get("/openapi.json").json()
        paths = set(schema["paths"].keys())
        assert "/api/projects" in paths
        assert "/api/projects/{project_id}" in paths

    def test_list_response_schema_points_at_summary(self, seeded_client):
        schema = seeded_client.get("/openapi.json").json()
        list_op = schema["paths"]["/api/projects"]["get"]
        ref = list_op["responses"]["200"]["content"]["application/json"]["schema"]
        assert ref.get("type") == "array"
        assert "ProjectSummary" in ref["items"]["$ref"]

    def test_detail_response_schema_points_at_detail(self, seeded_client):
        schema = seeded_client.get("/openapi.json").json()
        detail_op = schema["paths"]["/api/projects/{project_id}"]["get"]
        ref = detail_op["responses"]["200"]["content"]["application/json"]["schema"]
        assert "ProjectDetail" in ref["$ref"]
