"""Layer-3 coherence validator: session.status vs. referenced issue statuses.

See src/tripwire/core/validator.py:check_session_issue_coherence.
"""

from pathlib import Path

from tripwire.core.validator import (
    _COHERENCE_MATRIX,
    validate_project,
)


def test_matrix_shape():
    """Every session status in the matrix must list every known issue status."""
    expected_issue_statuses = {
        "backlog",
        "todo",
        "in_progress",
        "in_review",
        "verified",
        "done",
    }
    for session_status, row in _COHERENCE_MATRIX.items():
        missing = expected_issue_statuses - set(row.keys())
        assert not missing, f"matrix row {session_status!r} missing: {missing}"


def test_issue_behind_session_is_error(
    tmp_path_project: Path, save_test_issue, save_test_session
):
    """Session in_review + issue still todo → error (session is past the issue)."""
    save_test_issue(tmp_path_project, "TMP-1", status="todo")
    save_test_session(
        tmp_path_project,
        "session-one",
        issues=["TMP-1"],
        status="in_review",
    )

    report = validate_project(tmp_path_project)
    codes = [f.code for f in report.findings]
    assert "coherence/issue_status_lags_session" in codes
    lags = [
        f for f in report.findings if f.code == "coherence/issue_status_lags_session"
    ]
    assert lags[0].severity == "error"


def test_issue_ahead_of_session_is_warning(
    tmp_path_project: Path, save_test_issue, save_test_session
):
    """Session in_progress + issue already done → warning (issue ran ahead)."""
    save_test_issue(tmp_path_project, "TMP-1", status="done")
    save_test_session(
        tmp_path_project,
        "session-one",
        issues=["TMP-1"],
        status="executing",
    )

    report = validate_project(tmp_path_project)
    codes = [f.code for f in report.findings]
    assert "coherence/issue_status_ahead_of_session" in codes
    ahead = [
        f
        for f in report.findings
        if f.code == "coherence/issue_status_ahead_of_session"
    ]
    assert ahead[0].severity == "warning"


def test_coherence_passes_when_aligned(
    tmp_path_project: Path, save_test_issue, save_test_session
):
    """Session executing + issue in_progress → no coherence finding."""
    save_test_issue(tmp_path_project, "TMP-1", status="in_progress")
    save_test_session(
        tmp_path_project,
        "session-one",
        issues=["TMP-1"],
        status="executing",
    )

    report = validate_project(tmp_path_project)
    codes = [f.code for f in report.findings]
    assert "coherence/issue_status_lags_session" not in codes
    assert "coherence/issue_status_ahead_of_session" not in codes


def test_coherence_skips_off_lifecycle_statuses(
    tmp_path_project: Path, save_test_issue, save_test_session
):
    """Session.status == 'failed' is not in the matrix → no finding emitted."""
    save_test_issue(tmp_path_project, "TMP-1", status="todo")
    save_test_session(
        tmp_path_project,
        "session-one",
        issues=["TMP-1"],
        status="failed",
    )

    report = validate_project(tmp_path_project)
    codes = [f.code for f in report.findings]
    assert "coherence/issue_status_lags_session" not in codes
    assert "coherence/issue_status_ahead_of_session" not in codes
