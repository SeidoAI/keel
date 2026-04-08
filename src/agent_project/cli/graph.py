"""`agent-project graph` — render the dependency or concept graph.

Thin CLI wrapper over `core.dependency_graph` and `core.concept_graph`.
Reads from the cache (`graph/index.yaml`) when available, falls back to
a filesystem scan otherwise.

Output formats:
- `mermaid` (default) — `graph LR` flowchart for the Mermaid renderer
- `dot` — Graphviz DOT
- `json` — the computed graph as JSON (for the UI and programmatic use)
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from agent_project.core.concept_graph import build_full_graph
from agent_project.core.dependency_graph import (
    build_dependency_graph,
    to_dot,
    to_mermaid,
)
from agent_project.core.store import (
    ProjectNotFoundError,
    list_issues,
    load_project,
)


@click.command(name="graph")
@click.option(
    "--project-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=".",
    show_default=True,
    help="Path to the project root (contains project.yaml).",
)
@click.option(
    "--type",
    "graph_type",
    type=click.Choice(["deps", "concept"]),
    default="deps",
    show_default=True,
    help="`deps` = issue dependency graph; `concept` = full concept graph.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["mermaid", "dot", "json"]),
    default="mermaid",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Write to this file instead of stdout.",
)
@click.option(
    "--status-filter",
    default=None,
    help="Comma-separated issue statuses to include (default: all).",
)
def graph_cmd(
    project_dir: Path,
    graph_type: str,
    output_format: str,
    output: Path | None,
    status_filter: str | None,
) -> None:
    """Render the dependency or concept graph for a project.

    The dependency graph (`--type deps`) is the graph of issues connected
    by `blocked_by` relations, with cycle detection and a critical path.
    The concept graph (`--type concept`) is the full unified view: issues,
    concept nodes, and every edge type.
    """
    resolved = project_dir.expanduser().resolve()
    try:
        load_project(resolved)  # validates project.yaml is present
    except ProjectNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = _render(resolved, graph_type, output_format, status_filter)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        click.echo(rendered, nl=False)


def _render(
    project_dir: Path,
    graph_type: str,
    output_format: str,
    status_filter: str | None,
) -> str:
    if graph_type == "deps":
        issues = list_issues(project_dir)
        if status_filter:
            allowed = {s.strip() for s in status_filter.split(",") if s.strip()}
            issues = [i for i in issues if i.status in allowed]
        result = build_dependency_graph(issues)
        if output_format == "json":
            return (
                json.dumps(result.model_dump(mode="json", by_alias=True), indent=2)
                + "\n"
            )
        if output_format == "dot":
            return to_dot(result)
        return to_mermaid(result)

    # graph_type == "concept"
    result = build_full_graph(project_dir)
    if status_filter:
        allowed = {s.strip() for s in status_filter.split(",") if s.strip()}
        kept_ids = {n.id for n in result.nodes if not n.status or n.status in allowed}
        result.nodes = [n for n in result.nodes if n.id in kept_ids]
        result.edges = [
            e for e in result.edges if e.from_id in kept_ids and e.to_id in kept_ids
        ]
    if output_format == "json":
        return (
            json.dumps(result.model_dump(mode="json", by_alias=True), indent=2) + "\n"
        )
    if output_format == "dot":
        return _concept_to_dot(result)
    return _concept_to_mermaid(result)


def _concept_to_mermaid(result: object) -> str:
    """Render a FullGraphResult as a Mermaid flowchart.

    Concept nodes are rendered as rounded shapes, issues as rectangles.
    The rendering is intentionally simple — the UI's React Flow view is
    where the pretty layout lives.
    """
    lines = ["graph LR"]
    for node in result.nodes:  # type: ignore[attr-defined]
        label = (node.label or node.id).replace('"', "'")
        if node.kind == "node":
            lines.append(f'  {_safe_id(node.id)}(("{label}"))')
        else:
            lines.append(f'  {_safe_id(node.id)}["{label}"]')
    for edge in result.edges:  # type: ignore[attr-defined]
        lines.append(
            f"  {_safe_id(edge.from_id)} -->|{edge.type}| {_safe_id(edge.to_id)}"
        )
    return "\n".join(lines) + "\n"


def _concept_to_dot(result: object) -> str:
    """Render a FullGraphResult as Graphviz DOT."""
    lines = ["digraph concept {", "  rankdir=LR;"]
    for node in result.nodes:  # type: ignore[attr-defined]
        label = (node.label or node.id).replace('"', "'")
        shape = "ellipse" if node.kind == "node" else "box"
        lines.append(f'  "{node.id}" [label="{label}", shape={shape}];')
    for edge in result.edges:  # type: ignore[attr-defined]
        lines.append(f'  "{edge.from_id}" -> "{edge.to_id}" [label="{edge.type}"];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def _safe_id(raw: str) -> str:
    """Mermaid node IDs must be alphanumeric + underscore. Replace `-` with `_`."""
    return raw.replace("-", "_").replace(".", "_")
