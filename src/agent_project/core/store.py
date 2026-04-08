"""File-based CRUD for issues, project config, and comments.

This module is the only place that touches the filesystem for these entity
types. It uses the parser to split frontmatter from body and the model layer
to construct typed objects from the parsed dict.

Project config is read from `<project>/project.yaml` (no body, just YAML).
Issues live at `<project>/issues/<KEY>.yaml`.
Comments live at `<project>/docs/issues/<KEY>/comments/<sequence>-*.yaml`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from agent_project.core.parser import (
    ParseError,
    parse_frontmatter_body,
    serialize_frontmatter_body,
)
from agent_project.models.comment import Comment
from agent_project.models.issue import Issue
from agent_project.models.project import ProjectConfig

ISSUES_DIRNAME = "issues"
PROJECT_CONFIG_FILENAME = "project.yaml"
COMMENTS_DIRNAME = "comments"


# ============================================================================
# Project config
# ============================================================================


class ProjectNotFoundError(FileNotFoundError):
    """Raised when `project.yaml` is missing from the expected location."""


def load_project(project_dir: Path) -> ProjectConfig:
    """Load `<project_dir>/project.yaml` into a ProjectConfig.

    Raises:
        ProjectNotFoundError: if project.yaml is missing.
        ValueError: if the file cannot be parsed.
    """
    path = project_dir / PROJECT_CONFIG_FILENAME
    if not path.exists():
        raise ProjectNotFoundError(
            f"project.yaml not found at {path}. Run `agent-project init` first."
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(
            f"project.yaml must be a YAML mapping, got {type(raw).__name__}"
        )
    return ProjectConfig.model_validate(raw)


def save_project(project_dir: Path, config: ProjectConfig) -> None:
    """Write a ProjectConfig back to `<project_dir>/project.yaml`."""
    path = project_dir / PROJECT_CONFIG_FILENAME
    data = config.model_dump(mode="json", exclude_none=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


# ============================================================================
# Issues
# ============================================================================


def issue_path(project_dir: Path, key: str) -> Path:
    return project_dir / ISSUES_DIRNAME / f"{key}.yaml"


def load_issue(project_dir: Path, key: str) -> Issue:
    """Load `<project_dir>/issues/<key>.yaml` into an Issue model."""
    path = issue_path(project_dir, key)
    if not path.exists():
        raise FileNotFoundError(f"Issue file not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        frontmatter, body = parse_frontmatter_body(text)
    except ParseError as exc:
        raise ValueError(f"Could not parse {path}: {exc}") from exc
    return Issue.model_validate({**frontmatter, "body": body})


def save_issue(project_dir: Path, issue: Issue) -> None:
    """Serialise an Issue to `<project_dir>/issues/<id>.yaml`.

    Sets `updated_at` to now if it is unset.
    """
    if issue.updated_at is None:
        issue.updated_at = datetime.now()

    path = issue_path(project_dir, issue.id)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = issue.model_dump(mode="json", exclude={"body"}, exclude_none=True)
    text = serialize_frontmatter_body(data, issue.body)
    path.write_text(text, encoding="utf-8")


def list_issues(project_dir: Path) -> list[Issue]:
    """Load every issue file under `<project_dir>/issues/`.

    Files that fail to parse raise the parse error so callers can decide
    whether to skip them. The validator should be the gate that catches
    invalid files at scan time.
    """
    issues_dir = project_dir / ISSUES_DIRNAME
    if not issues_dir.is_dir():
        return []
    issues: list[Issue] = []
    for path in sorted(issues_dir.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter_body(text)
        issues.append(Issue.model_validate({**frontmatter, "body": body}))
    return issues


def issue_exists(project_dir: Path, key: str) -> bool:
    return issue_path(project_dir, key).exists()


# ============================================================================
# Comments
# ============================================================================


def comments_dir(project_dir: Path, issue_key: str) -> Path:
    return project_dir / "docs" / ISSUES_DIRNAME / issue_key / COMMENTS_DIRNAME


def load_comments(project_dir: Path, issue_key: str) -> list[Comment]:
    """Load every comment under `<project_dir>/docs/issues/<key>/comments/`."""
    cdir = comments_dir(project_dir, issue_key)
    if not cdir.is_dir():
        return []
    comments: list[Comment] = []
    for path in sorted(cdir.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter_body(text)
        comments.append(Comment.model_validate({**frontmatter, "body": body}))
    return comments


def save_comment(project_dir: Path, comment: Comment, filename: str) -> None:
    """Save one comment under `<project_dir>/docs/issues/<key>/comments/<filename>`.

    The caller picks the filename (e.g. `001-start-2026-03-26.yaml`) so the
    sequence number convention is preserved.
    """
    cdir = comments_dir(project_dir, comment.issue_key)
    cdir.mkdir(parents=True, exist_ok=True)
    path = cdir / filename
    data = comment.model_dump(mode="json", exclude={"body"}, exclude_none=True)
    text = serialize_frontmatter_body(data, comment.body)
    path.write_text(text, encoding="utf-8")
