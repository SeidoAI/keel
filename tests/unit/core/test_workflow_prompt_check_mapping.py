"""Prompt-check status mapping (KUI-122).

Each PM-skill slash command file declares ``fires_at: <status-id>``
in its YAML frontmatter. The workflow registry indexes commands by
status so the gate runner (KUI-159) can ask "what prompt-checks fire
at status X?" and the well-formedness validator can resolve
workflow.yaml's ``prompt_checks: [...]`` refs against the registry.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent


def test_collect_prompt_checks_returns_packaged_session_commands(
    tmp_path: Path,
) -> None:
    """The packaged ``templates/commands/`` directory ships PM session
    commands with ``fires_at:`` declared. The collector must surface
    every one."""
    from tripwire.core.workflow.prompt_checks import collect_prompt_checks

    pcs = collect_prompt_checks(tmp_path)
    ids = {pc.id for pc in pcs}
    expected = {
        "pm-session-create",
        "pm-session-queue",
        "pm-session-spawn",
        "pm-session-review",
        "pm-session-complete",
    }
    missing = expected - ids
    assert not missing, (
        f"PM session commands missing `fires_at:` frontmatter: {missing}"
    )


def test_collect_prompt_checks_filters_non_workflow_commands(
    tmp_path: Path,
) -> None:
    """Slash commands without ``fires_at:`` (general PM tools like
    pm-validate, pm-status) are not surfaced through the
    workflow-status registry."""
    from tripwire.core.workflow.prompt_checks import collect_prompt_checks

    pcs = collect_prompt_checks(tmp_path)
    ids = {pc.id for pc in pcs}
    # These are PM tools, not workflow-status prompt-checks.
    assert "pm-validate" not in ids
    assert "pm-status" not in ids
    assert "pm-edit" not in ids


def test_known_prompt_check_ids_returns_packaged_set(tmp_path: Path) -> None:
    from tripwire.core.workflow.registry import known_prompt_check_ids

    ids = known_prompt_check_ids(tmp_path)
    # Sanity check on the workflow.yaml.j2 references.
    assert "pm-session-queue" in ids
    assert "pm-session-spawn" in ids
    assert "pm-session-review" in ids


def test_prompt_checks_for_status_groups_by_fires_at(tmp_path: Path) -> None:
    from tripwire.core.workflow.registry import prompt_checks_for_status

    queued = prompt_checks_for_status(tmp_path, "queued")
    assert "pm-session-queue" in queued
    in_review = prompt_checks_for_status(tmp_path, "in_review")
    assert "pm-session-review" in in_review


def test_project_local_override_wins_over_packaged(tmp_path: Path) -> None:
    """Project-local ``.tripwire/commands/<name>.md`` shadows the
    packaged default — the override wins for that command id."""
    from tripwire.core.workflow.prompt_checks import collect_prompt_checks

    overrides = tmp_path / ".tripwire" / "commands"
    overrides.mkdir(parents=True)
    (overrides / "pm-session-spawn.md").write_text(
        dedent(
            """\
            ---
            name: pm-session-spawn
            fires_at: planned
            description: project-local override
            ---

            override body
            """
        ),
        encoding="utf-8",
    )
    pcs = {pc.id: pc for pc in collect_prompt_checks(tmp_path)}
    assert pcs["pm-session-spawn"].fires_at == "planned"


def test_workflow_well_formed_resolves_prompt_check_refs(tmp_path: Path) -> None:
    """workflow.yaml's ``prompt_checks: [...]`` refs against ids that
    are not declared via ``fires_at:`` produce a
    ``workflow/unknown_prompt_check`` finding."""
    (tmp_path / "workflow.yaml").write_text(
        dedent(
            """\
            workflows:
              w:
                actor: a
                trigger: t
                statuses:
                  - id: s1
                    next: s2
                    prompt_checks: [pm-session-queue, does-not-exist]
                  - id: s2
                    terminal: true
            """
        ),
        encoding="utf-8",
    )
    # Need a project.yaml so the validator's project loader doesn't
    # complain — this test is about workflow refs only.
    (tmp_path / "project.yaml").write_text(
        "name: test\nkey_prefix: TST\nbase_branch: main\nstatuses: [planned]\n"
        "status_transitions:\n  planned: []\nrepos: {}\nnext_issue_number: 1\n"
        "next_session_number: 1\n",
        encoding="utf-8",
    )
    from tripwire.core.validator import load_context
    from tripwire.core.validator.checks.workflow import check_workflow_well_formed

    ctx = load_context(tmp_path)
    findings = check_workflow_well_formed(ctx)
    codes = [f.code for f in findings]
    assert "workflow/unknown_prompt_check" in codes
    # The known one (pm-session-queue) does NOT fire a finding.
    msgs = [f.message for f in findings if f.code == "workflow/unknown_prompt_check"]
    assert any("does-not-exist" in m for m in msgs)
    assert not any("pm-session-queue" in m for m in msgs)
