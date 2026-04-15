"""Shared pytest fixtures."""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def tmp_project_manifest(tmp_path: Path):
    """Factory creating a minimal project with a custom manifest for
    validator testing."""

    def _factory(artifacts: list[dict]) -> Path:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "project.yaml").write_text(
            "name: tmp\nslug: tmp\nkey_prefix: TMP\nnext_issue_number: 1\n"
            "next_session_number: 1\nschema_version: 1\n"
        )
        (project_dir / "issues").mkdir()
        (project_dir / "nodes").mkdir()
        (project_dir / "sessions").mkdir()
        templates = project_dir / "templates" / "artifacts"
        templates.mkdir(parents=True)
        (templates / "manifest.yaml").write_text(
            yaml.safe_dump({"artifacts": artifacts})
        )
        return project_dir

    return _factory
