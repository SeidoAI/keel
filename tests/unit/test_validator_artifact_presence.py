"""Tests for `check_artifact_presence` (KUI-110 + KUI-158).

The rule gates artifact enforcement on ``status == SessionStatus.COMPLETED``.
The previous ``MERGED_STATUSES`` frozenset abstraction was removed in the
v0.9 prune (KUI-158) once ``LEGACY_COMPLETED`` was deleted — there is now
only one terminal-success state.
"""

from __future__ import annotations

from pathlib import Path

from tests.unit.test_validator import (  # type: ignore[import-not-found]
    write_project_yaml,
    write_session,
)
from tripwire.core.validator import validate_project


def _write_minimal_manifest(project_dir: Path) -> None:
    """Write a minimal artifact manifest requiring `developer.md`."""
    manifest_dir = project_dir / "templates" / "artifacts"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "manifest.yaml").write_text(
        "artifacts:\n"
        "  - name: developer\n"
        "    file: developer.md\n"
        "    template: developer.md.j2\n"
        "    required: true\n"
        "    produced_at: completion\n"
        "    produced_by: execution-agent\n"
        "    owned_by: execution-agent\n",
        encoding="utf-8",
    )


def test_completed_session_missing_artifact_flagged(tmp_path: Path) -> None:
    """Session at completed without required artifact → artifact/missing."""
    write_project_yaml(tmp_path)
    _write_minimal_manifest(tmp_path)
    write_session(tmp_path, "done-sess", status="completed")

    report = validate_project(tmp_path, strict=True, fix=False)

    artifact_errors = [r for r in report.errors if r.code == "artifact/missing"]
    assert artifact_errors, (
        f"expected artifact/missing error, got "
        f"{[(r.code, r.message) for r in report.errors]}"
    )


def test_non_terminal_session_skips_artifact_check(tmp_path: Path) -> None:
    """Session at executing → artifact-presence rule skips it (not yet terminal)."""
    write_project_yaml(tmp_path)
    _write_minimal_manifest(tmp_path)
    write_session(tmp_path, "live-sess", status="executing")

    report = validate_project(tmp_path, strict=True, fix=False)

    artifact_errors = [r for r in report.errors if r.code == "artifact/missing"]
    assert artifact_errors == [], (
        f"executing session should not be artifact-checked, got {artifact_errors}"
    )
