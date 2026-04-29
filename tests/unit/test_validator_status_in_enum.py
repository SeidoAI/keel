"""Tests for the upstream-enum status check rules (KUI-110 Phase 2.4).

These rules are the belt-and-suspenders layer that catches statuses
not in the upstream Python enum. Post-Phase 2.1 the typed schema
(``AgentSession.status: SessionStatus``) rejects invalid values during
``model_validate``, so most invalid YAML never makes it past the
loader — the load-time error code is ``session/schema_invalid``. The
``status/invalid_enum`` rule still has belt-and-suspenders value for
issues (``Issue.status`` remains a plain ``str``) and for any future
session in-memory mutation that bypasses validation.
"""

from __future__ import annotations

from pathlib import Path

from tests.unit.test_validator import (  # type: ignore[import-not-found]
    write_issue,
    write_project_yaml,
    write_session,
)
from tripwire.core.validator import (
    ValidationContext,
    check_session_status_in_enum,
    validate_project,
)


def test_session_with_invalid_status_blocked_at_load(tmp_path: Path) -> None:
    """A session with status not in SessionStatus is rejected at load
    time (typed schema field). Either ``status/invalid_enum`` or
    ``session/schema_invalid`` must be reported for the bad session."""
    write_project_yaml(tmp_path)
    write_session(tmp_path, "good-sess", status="executing")
    write_session(tmp_path, "bad-sess", status="nonsense_value")

    report = validate_project(tmp_path, strict=True, fix=False)

    flagged_for_bad = [r.code for r in report.errors if "bad-sess" in (r.file or "")]
    assert any(
        c in {"status/invalid_enum", "session/schema_invalid"} for c in flagged_for_bad
    ), f"expected schema or rule error on bad-sess, got {flagged_for_bad}"

    flagged_for_good = [r.code for r in report.errors if "good-sess" in (r.file or "")]
    assert "status/invalid_enum" not in flagged_for_good
    assert "session/schema_invalid" not in flagged_for_good


def test_session_with_legacy_done_status_blocked(tmp_path: Path) -> None:
    """`status: done` is the exact failure mode that motivated KUI-110."""
    write_project_yaml(tmp_path)
    write_session(tmp_path, "legacy-done", status="done")

    report = validate_project(tmp_path, strict=True, fix=False)

    flagged = [r.code for r in report.errors if "legacy-done" in (r.file or "")]
    assert any(
        c in {"status/invalid_enum", "session/schema_invalid"} for c in flagged
    ), f"expected legacy-done to be rejected, got {flagged}"


def test_check_session_status_in_enum_catches_in_memory_mutation() -> None:
    """If a session model is mutated in-memory to an invalid status
    (Pydantic doesn't validate on assignment by default), the rule
    catches it."""
    from tripwire.core.validator import LoadedEntity
    from tripwire.models.session import AgentSession

    sess = AgentSession.model_validate(
        {
            "id": "mutated",
            "name": "Test",
            "agent": "backend-coder",
            "issues": [],
            "repos": [],
            "status": "completed",
        }
    )
    # Force the field past the typed-enum guard. Pydantic v2 doesn't
    # validate on assignment by default, so this models the bypass.
    object.__setattr__(sess, "status", "nonsense_value")

    entity = LoadedEntity(
        rel_path="sessions/mutated/session.yaml",
        raw_frontmatter={},
        body="",
        model=sess,
    )
    ctx = ValidationContext(project_dir=Path("/tmp/proj"))
    ctx.sessions = [entity]

    results = check_session_status_in_enum(ctx)
    assert any(r.code == "status/invalid_enum" for r in results), (
        f"expected status/invalid_enum on mutated session, got "
        f"{[r.code for r in results]}"
    )


def test_issue_with_invalid_status_flagged(tmp_path: Path) -> None:
    """``Issue.status`` is still a plain ``str``, so the validator rule
    is the only layer that catches an invalid issue status."""
    write_project_yaml(tmp_path)
    write_issue(tmp_path, "TST-1", status="todo")
    write_issue(tmp_path, "TST-2", status="ghost_state")

    report = validate_project(tmp_path, strict=True, fix=False)

    matches = [r for r in report.errors if r.code == "status/invalid_enum"]
    flagged_files = [m.file for m in matches]
    assert any("TST-2" in (f or "") for f in flagged_files), (
        f"expected error on TST-2, got files={flagged_files}"
    )
    assert not any("TST-1" in (f or "") for f in flagged_files)


def test_valid_status_no_error(tmp_path: Path) -> None:
    """Sessions and issues at upstream-canonical statuses pass clean."""
    write_project_yaml(tmp_path)
    write_session(tmp_path, "ok-sess", status="completed")
    write_issue(tmp_path, "TST-3", status="done")  # done IS valid for issues

    report = validate_project(tmp_path, strict=True, fix=False)

    invalid_enum_errors = [r for r in report.errors if r.code == "status/invalid_enum"]
    assert invalid_enum_errors == [], (
        f"expected no status/invalid_enum errors, got "
        f"{[(r.file, r.message) for r in invalid_enum_errors]}"
    )
