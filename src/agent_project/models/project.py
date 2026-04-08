"""ProjectConfig model — represents `<project>/project.yaml`.

The project config is the entry point for every CLI command and the
authoritative source for repo registry, status flow, label categories,
graph settings, the orchestration default, and the next-issue counter
used by `agent-project next-key`.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RepoEntry(BaseModel):
    """One repo in `project.yaml.repos`.

    The repo is keyed in the parent dict by GitHub slug; the entry holds the
    optional local clone path used for fast freshness checks.
    """

    model_config = ConfigDict(extra="forbid")

    local: str | None = None


class GraphSettings(BaseModel):
    """`project.yaml.graph` — concept graph settings."""

    model_config = ConfigDict(extra="forbid")

    node_types: list[str] = Field(default_factory=list)
    auto_index: bool = True


class LabelCategories(BaseModel):
    """`project.yaml.label_categories` — categorised labels.

    Each category is a list of allowed values; an empty list means "any
    label in this category is allowed".
    """

    model_config = ConfigDict(extra="forbid")

    executor: list[str] = Field(default_factory=list)
    verifier: list[str] = Field(default_factory=list)
    domain: list[str] = Field(default_factory=list)
    agent: list[str] = Field(default_factory=list)


class OrchestrationConfig(BaseModel):
    """`project.yaml.orchestration` — orchestration defaults for the project.

    The named pattern is loaded from `<project>/orchestration/<name>.yaml`.
    Sessions can override either the named pattern or individual fields.
    """

    model_config = ConfigDict(extra="allow")

    default_pattern: str = "default"
    plan_approval_required: bool = False
    auto_merge_on_pass: bool = False


class ProjectConfig(BaseModel):
    """The project's root config, parsed from `<project>/project.yaml`."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str
    key_prefix: str
    description: str | None = None
    base_branch: str = "test"
    environments: list[str] = Field(default_factory=list)

    repos: dict[str, RepoEntry] = Field(default_factory=dict)

    statuses: list[str] = Field(default_factory=list)
    status_transitions: dict[str, list[str]] = Field(default_factory=dict)

    label_categories: LabelCategories = Field(default_factory=LabelCategories)

    graph: GraphSettings = Field(default_factory=GraphSettings)

    orchestration: OrchestrationConfig = Field(default_factory=OrchestrationConfig)

    next_issue_number: int = 1
    next_session_number: int = 1

    created_at: datetime | None = None

    # Free-form per-project metadata, never used by the package itself.
    metadata: dict[str, Any] = Field(default_factory=dict)
