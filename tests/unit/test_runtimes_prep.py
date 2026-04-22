"""Tests for the runtime prep pipeline."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(
        [
            "git", "-c", "user.name=t", "-c", "user.email=t@t",
            "commit", "--allow-empty", "-q", "-m", "init",
        ],
        cwd=path, check=True,
    )


class TestResolveWorktrees:
    def test_creates_one_worktree_per_repo(
        self, tmp_path, tmp_path_project, save_test_session
    ):
        from tripwire.runtimes.prep import resolve_worktrees

        code_clone = tmp_path / "code-clone"
        code_clone.mkdir()
        _init_repo(code_clone)

        project_clone = tmp_path / "project-clone"
        project_clone.mkdir()
        _init_repo(project_clone)

        save_test_session(
            tmp_path_project,
            "s1",
            status="queued",
            repos=[
                {"repo": "SeidoAI/code", "base_branch": "main"},
                {"repo": "SeidoAI/project", "base_branch": "main"},
            ],
        )

        from tripwire.core.session_store import load_session

        session = load_session(tmp_path_project, "s1")

        def fake_resolve(_resolved: Path, repo: str) -> Path:
            return code_clone if repo == "SeidoAI/code" else project_clone

        with patch(
            "tripwire.runtimes.prep._resolve_clone_path",
            side_effect=fake_resolve,
        ):
            entries = resolve_worktrees(
                session=session,
                project_dir=tmp_path_project,
                branch="feat/s1",
                base_ref="main",
            )

        assert len(entries) == 2
        assert entries[0].repo == "SeidoAI/code"
        assert entries[1].repo == "SeidoAI/project"
        for entry in entries:
            assert Path(entry.worktree_path).is_dir()

    def test_first_repo_is_the_code_worktree(
        self, tmp_path, tmp_path_project, save_test_session
    ):
        from tripwire.runtimes.prep import resolve_worktrees

        code_clone = tmp_path / "code-clone"
        code_clone.mkdir()
        _init_repo(code_clone)

        save_test_session(
            tmp_path_project,
            "s1",
            status="queued",
            repos=[{"repo": "SeidoAI/code", "base_branch": "main"}],
        )

        from tripwire.core.session_store import load_session

        session = load_session(tmp_path_project, "s1")

        with patch(
            "tripwire.runtimes.prep._resolve_clone_path",
            return_value=code_clone,
        ):
            entries = resolve_worktrees(
                session=session,
                project_dir=tmp_path_project,
                branch="feat/s1",
                base_ref="main",
            )

        assert entries[0].repo == "SeidoAI/code"

    def test_missing_clone_path_errors(
        self, tmp_path_project, save_test_session
    ):
        from tripwire.runtimes.prep import resolve_worktrees

        save_test_session(
            tmp_path_project,
            "s1",
            status="queued",
            repos=[{"repo": "SeidoAI/missing", "base_branch": "main"}],
        )

        from tripwire.core.session_store import load_session

        session = load_session(tmp_path_project, "s1")

        with patch(
            "tripwire.runtimes.prep._resolve_clone_path",
            return_value=None,
        ):
            with pytest.raises(RuntimeError, match="No local clone"):
                resolve_worktrees(
                    session=session,
                    project_dir=tmp_path_project,
                    branch="feat/s1",
                    base_ref="main",
                )
