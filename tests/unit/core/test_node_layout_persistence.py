"""Unit tests for the optional `layout: {x, y}` field on ConceptNode (KUI-104).

The Concept Graph screen seeds positions with d3-force on first load, then
persists each node's resting (x, y) into its YAML so a reload uses the
stored layout instead of re-running the force simulation. This module
covers the schema half of that round trip; the route-level half lives in
`tests/ui/routes/test_nodes_routes.py::TestPatchLayout`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tripwire.core.node_store import load_node, save_node
from tripwire.models import ConceptNode, NodeLayout


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    (tmp_path / "nodes").mkdir(parents=True)
    return tmp_path


def _node(node_id: str = "user-model", layout: NodeLayout | None = None) -> ConceptNode:
    return ConceptNode(
        id=node_id,
        type="model",
        name="User",
        layout=layout,
    )


class TestNodeLayoutField:
    def test_default_layout_is_none(self) -> None:
        node = _node()
        assert node.layout is None

    def test_layout_round_trips_through_yaml(self, project_dir: Path) -> None:
        node = _node(layout=NodeLayout(x=120.5, y=-44.0))
        save_node(project_dir, node)
        loaded = load_node(project_dir, "user-model")
        assert loaded.layout is not None
        assert loaded.layout.x == pytest.approx(120.5)
        assert loaded.layout.y == pytest.approx(-44.0)

    def test_node_without_layout_round_trips(self, project_dir: Path) -> None:
        save_node(project_dir, _node())
        loaded = load_node(project_dir, "user-model")
        assert loaded.layout is None

    def test_layout_omitted_from_yaml_when_none(self, project_dir: Path) -> None:
        save_node(project_dir, _node())
        raw = (project_dir / "nodes" / "user-model.yaml").read_text()
        assert "layout:" not in raw

    def test_layout_rejects_non_numeric(self) -> None:
        with pytest.raises(ValueError):
            NodeLayout(x="bad", y=0.0)  # type: ignore[arg-type]
