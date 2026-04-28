import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GraphSidebar } from "@/features/graph/GraphSidebar";
import type { ReactFlowGraph } from "@/lib/api/endpoints/graph";

function graph(): ReactFlowGraph {
  return {
    nodes: [
      {
        id: "user-model",
        type: "concept",
        position: { x: 0, y: 0 },
        data: { label: "User model", type: "model" },
      },
      {
        id: "auth-flow",
        type: "concept",
        position: { x: 0, y: 0 },
        data: { label: "Auth flow", type: "decision" },
      },
      {
        id: "session-svc",
        type: "concept",
        position: { x: 0, y: 0 },
        data: { label: "Session service", type: "service" },
      },
      {
        id: "KUI-1",
        type: "issue",
        position: { x: 0, y: 0 },
        data: { label: "Login endpoint" },
      },
    ],
    edges: [],
    meta: {
      kind: "concept",
      focus: null,
      upstream: false,
      downstream: false,
      depth: null,
      node_count: 4,
      edge_count: 0,
      orphans: [],
    },
  };
}

describe("GraphSidebar", () => {
  afterEach(() => cleanup());

  it("groups concept nodes by their type and lists each name", () => {
    render(<GraphSidebar graph={graph()} selectedId={null} onSelect={() => {}} />);
    // Group headers (Geist Mono uppercase by spec).
    expect(screen.getByText(/^model$/i)).toBeInTheDocument();
    expect(screen.getByText(/^decision$/i)).toBeInTheDocument();
    expect(screen.getByText(/^service$/i)).toBeInTheDocument();
    // Concept names render under their group.
    expect(screen.getByRole("button", { name: /User model/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Auth flow/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Session service/ })).toBeInTheDocument();
  });

  it("excludes issue-typed nodes (kind=issue) from the outline tree", () => {
    render(<GraphSidebar graph={graph()} selectedId={null} onSelect={() => {}} />);
    expect(screen.queryByRole("button", { name: /Login endpoint/ })).toBeNull();
  });

  it("highlights the currently-selected concept", () => {
    render(<GraphSidebar graph={graph()} selectedId="auth-flow" onSelect={() => {}} />);
    const btn = screen.getByRole("button", { name: /Auth flow/ });
    expect(btn).toHaveAttribute("aria-current", "true");
  });

  it("invokes onSelect when a concept row is clicked", () => {
    const onSelect = vi.fn();
    render(<GraphSidebar graph={graph()} selectedId={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /User model/ }));
    expect(onSelect).toHaveBeenCalledWith("user-model");
  });
});
