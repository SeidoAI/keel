"""KUI-146 (D4) — semantic_coverage lint.

For each active issue, warn if its acceptance criteria reference fewer
concept nodes than the project-type threshold (default 1).

The lint inspects only the ``## Acceptance criteria`` section of the
issue body (a Context-only ``[[node]]`` reference doesn't count). This
keeps the signal aligned with what's actually required to land the
issue.
"""

from pathlib import Path

from tripwire.core.validator import load_context
from tripwire.core.validator.lint import semantic_coverage


def _body(*, context_refs: str = "", ac_refs: str = "") -> str:
    return (
        f"## Context\n{context_refs}\n\n## Implements\nx\n\n"
        "## Repo scope\nx\n\n## Requirements\nx\n\n"
        "## Execution constraints\nstop and ask.\n\n"
        f"## Acceptance criteria\n- [ ] thing {ac_refs}\n\n"
        "## Test plan\n```\nuv run pytest\n```\n\n"
        "## Dependencies\nnone\n\n## Definition of Done\n- [ ] done\n"
    )


def test_active_issue_with_no_ac_refs_warns(
    tmp_path_project: Path, save_test_issue, save_test_node
):
    save_test_node(tmp_path_project, node_id="auth-system", name="Auth System")
    save_test_issue(
        tmp_path_project,
        key="TMP-1",
        status="in_progress",
        body=_body(context_refs="[[auth-system]]", ac_refs=""),
    )

    ctx = load_context(tmp_path_project)
    results = semantic_coverage.check(ctx)
    assert any(r.code == "semantic_coverage/below_threshold" for r in results)
    finding = next(
        r for r in results if r.code == "semantic_coverage/below_threshold"
    )
    assert finding.severity == "warning"
    assert "TMP-1" in finding.message


def test_active_issue_with_one_ac_ref_passes(
    tmp_path_project: Path, save_test_issue, save_test_node
):
    save_test_node(tmp_path_project, node_id="auth-system", name="Auth System")
    save_test_issue(
        tmp_path_project,
        key="TMP-1",
        status="in_progress",
        body=_body(ac_refs="against [[auth-system]]"),
    )

    ctx = load_context(tmp_path_project)
    assert semantic_coverage.check(ctx) == []


def test_done_issue_skipped(
    tmp_path_project: Path, save_test_issue, save_test_node
):
    save_test_node(tmp_path_project, node_id="auth-system", name="Auth System")
    save_test_issue(
        tmp_path_project,
        key="TMP-1",
        status="done",
        body=_body(),
    )

    ctx = load_context(tmp_path_project)
    assert semantic_coverage.check(ctx) == []


def test_canceled_issue_skipped(
    tmp_path_project: Path, save_test_issue, save_test_node
):
    save_test_node(tmp_path_project, node_id="auth-system", name="Auth System")
    save_test_issue(
        tmp_path_project,
        key="TMP-1",
        status="canceled",
        body=_body(),
    )

    ctx = load_context(tmp_path_project)
    assert semantic_coverage.check(ctx) == []
