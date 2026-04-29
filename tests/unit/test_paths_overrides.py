"""Project override paths added in v0.7b (resolve_command_path, etc.)."""

from tripwire.core.paths import (
    project_commands_dir,
    project_spawn_dir,
    resolve_command_path,
    tripwire_dir,
)


def test_tripwire_dir_structure(tmp_path):
    assert tripwire_dir(tmp_path) == tmp_path / ".tripwire"
    assert project_commands_dir(tmp_path) == tmp_path / ".tripwire" / "commands"
    assert project_spawn_dir(tmp_path) == tmp_path / ".tripwire" / "spawn"


def test_resolve_command_falls_back_to_tripwire_default(tmp_path):
    result = resolve_command_path(tmp_path, "pm-scope")
    assert result.name == "pm-scope.md"
    # Must point into the installed tripwire package's templates dir.
    import tripwire

    expected_parent = (
        __import__("pathlib").Path(tripwire.__file__).parent / "templates" / "commands"
    )
    assert result.parent == expected_parent


def test_resolve_command_prefers_project_override(tmp_path):
    override_dir = tmp_path / ".tripwire" / "commands"
    override_dir.mkdir(parents=True)
    (override_dir / "pm-scope.md").write_text("# custom", encoding="utf-8")

    result = resolve_command_path(tmp_path, "pm-scope")
    assert result == override_dir / "pm-scope.md"
    assert result.read_text() == "# custom"


def test_resolve_command_unknown_name_returns_nonexistent_package_path(tmp_path):
    """If the command doesn't exist anywhere, return the tripwire-template path.

    The caller decides whether a missing file is an error. This keeps the
    resolver side-effect-free.
    """
    result = resolve_command_path(tmp_path, "does-not-exist")
    assert result.name == "does-not-exist.md"
    assert not result.exists()


# --- session_plan_path: subdir-canonical with flat-fallback (KUI-110 follow-up) ---


def test_session_plan_path_returns_subdir_when_present(tmp_path):
    """Modern (post-KUI-110) layout: plan.md under sessions/<sid>/artifacts/."""
    from tripwire.core.paths import session_plan_path

    sd = tmp_path / "sessions" / "s1"
    (sd / "artifacts").mkdir(parents=True)
    subdir_plan = sd / "artifacts" / "plan.md"
    subdir_plan.write_text("# subdir plan\n", encoding="utf-8")

    assert session_plan_path(tmp_path, "s1") == subdir_plan


def test_session_plan_path_falls_back_to_flat_for_legacy(tmp_path):
    """Legacy session: plan.md at flat sessions/<sid>/plan.md, no artifacts/ dir."""
    from tripwire.core.paths import session_plan_path

    sd = tmp_path / "sessions" / "s1"
    sd.mkdir(parents=True)
    flat_plan = sd / "plan.md"
    flat_plan.write_text("# flat plan\n", encoding="utf-8")

    assert session_plan_path(tmp_path, "s1") == flat_plan


def test_session_plan_path_prefers_subdir_when_both_exist(tmp_path):
    """Belt-and-suspenders: subdir wins on a transitional session that has both."""
    from tripwire.core.paths import session_plan_path

    sd = tmp_path / "sessions" / "s1"
    (sd / "artifacts").mkdir(parents=True)
    flat_plan = sd / "plan.md"
    subdir_plan = sd / "artifacts" / "plan.md"
    flat_plan.write_text("# flat\n", encoding="utf-8")
    subdir_plan.write_text("# subdir\n", encoding="utf-8")

    assert session_plan_path(tmp_path, "s1") == subdir_plan


def test_session_plan_path_returns_flat_for_nonexistent_session(tmp_path):
    """No session dir on disk yet: resolver returns the flat path (callers
    that need the file to actually exist check that themselves)."""
    from tripwire.core.paths import session_plan_path

    p = session_plan_path(tmp_path, "never-created")
    # Doesn't crash; returns flat (back-compat default for callers that
    # are about to write the file).
    assert p == tmp_path / "sessions" / "never-created" / "plan.md"
    assert not p.exists()
