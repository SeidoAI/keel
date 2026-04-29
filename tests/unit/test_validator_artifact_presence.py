"""Tests for `check_artifact_presence` and the `MERGED_STATUSES` constant
(KUI-110 Phase 2.3).

The rule used to gate on a literal ``"completed"`` string. Phase 2.3
extracts a module-level frozenset so the gate is one place to update if
v1 ever introduces additional terminal-success statuses (e.g. a separate
``done`` after post-merge cleanup ships in some future release).
"""

from __future__ import annotations

from pathlib import Path

from tripwire.core.validator import MERGED_STATUSES, validate_project
from tripwire.models.enums import SessionStatus
from tests.unit.test_validator import (  # type: ignore[import-not-found]
    write_project_yaml,
    write_session,
)


def test_merged_statuses_constant_is_frozenset_of_completed() -> None:
    """`MERGED_STATUSES` is the single place that decides which statuses
    require artifact-presence enforcement. v1 baseline: just COMPLETED."""
    assert isinstance(MERGED_STATUSES, frozenset)
    assert SessionStatus.COMPLETED in MERGED_STATUSES


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
