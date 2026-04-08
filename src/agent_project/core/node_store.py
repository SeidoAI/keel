"""File-based CRUD for concept nodes.

Concept nodes live at `<project>/graph/nodes/<id>.yaml`. The filename matches
the node id (slug), and the file format is YAML frontmatter + optional
Markdown body — the same format as issues, parsed via `core/parser.py`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agent_project.core.parser import (
    ParseError,
    parse_frontmatter_body,
    serialize_frontmatter_body,
)
from agent_project.models.node import ConceptNode

NODES_DIRNAME = "graph/nodes"


def node_path(project_dir: Path, node_id: str) -> Path:
    return project_dir / NODES_DIRNAME / f"{node_id}.yaml"


def load_node(project_dir: Path, node_id: str) -> ConceptNode:
    """Load `<project_dir>/graph/nodes/<node_id>.yaml` into a ConceptNode."""
    path = node_path(project_dir, node_id)
    if not path.exists():
        raise FileNotFoundError(f"Concept node file not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        frontmatter, body = parse_frontmatter_body(text)
    except ParseError as exc:
        raise ValueError(f"Could not parse {path}: {exc}") from exc
    return ConceptNode.model_validate({**frontmatter, "body": body})


def save_node(project_dir: Path, node: ConceptNode) -> None:
    """Serialise a ConceptNode to `<project_dir>/graph/nodes/<id>.yaml`.

    Sets `updated_at` to now if it is unset.
    """
    if node.updated_at is None:
        node.updated_at = datetime.now()

    path = node_path(project_dir, node.id)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = node.model_dump(mode="json", exclude={"body"}, exclude_none=True)
    text = serialize_frontmatter_body(data, node.body)
    path.write_text(text, encoding="utf-8")


def list_nodes(project_dir: Path) -> list[ConceptNode]:
    """Load every node file under `<project_dir>/graph/nodes/`."""
    nodes_dir = project_dir / NODES_DIRNAME
    if not nodes_dir.is_dir():
        return []
    nodes: list[ConceptNode] = []
    for path in sorted(nodes_dir.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter_body(text)
        nodes.append(ConceptNode.model_validate({**frontmatter, "body": body}))
    return nodes


def node_exists(project_dir: Path, node_id: str) -> bool:
    return node_path(project_dir, node_id).exists()


def delete_node(project_dir: Path, node_id: str) -> None:
    """Delete a concept node file. No-op if the file does not exist."""
    path = node_path(project_dir, node_id)
    if path.exists():
        path.unlink()
