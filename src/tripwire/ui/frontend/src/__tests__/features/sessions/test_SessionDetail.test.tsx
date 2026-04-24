import { cleanup, fireEvent, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { Link, Route } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { SessionDetail } from "@/features/sessions/SessionDetail";
import type { ArtifactManifest } from "@/lib/api/endpoints/artifacts";
import type { IssueDetail } from "@/lib/api/endpoints/issues";
import type { SessionDetail as SessionDetailType } from "@/lib/api/endpoints/sessions";
import { queryKeys } from "@/lib/api/queryKeys";
import {
  makeArtifactSpec,
  makeIssueDetail,
  makeRepoBinding,
  makeSessionDetail,
} from "../../mocks/fixtures";
import { server } from "../../mocks/server";
import { makeTestQueryClient, renderWithProviders } from "../../test-utils";

function clickTab(el: HTMLElement) {
  // Radix Tabs trigger uses onMouseDown + onClick; jsdom's fireEvent.click
  // alone doesn't always activate the trigger. Fire the full press sequence.
  fireEvent.mouseDown(el, { button: 0 });
  fireEvent.mouseUp(el, { button: 0 });
  fireEvent.click(el);
}

function fixtureSession(overrides: Partial<SessionDetailType> = {}): SessionDetailType {
  return makeSessionDetail({
    id: "sess-a",
    name: "Foundation packaging",
    agent: "backend-coder",
    issues: ["KUI-1"],
    estimated_size: "M",
    repos: [makeRepoBinding()],
    task_progress: { done: 1, total: 3 },
    plan_md: "# Plan\n\nContent here.",
    grouping_rationale: "Grouped because they share an API surface.",
    ...overrides,
  });
}

function fixtureIssue(): IssueDetail {
  return makeIssueDetail({
    id: "KUI-1",
    title: "First issue",
  });
}

function fixtureManifest(): ArtifactManifest {
  return {
    artifacts: [
      makeArtifactSpec({ name: "plan", file: "plan.md", template: "plan" }),
      makeArtifactSpec({
        name: "task-checklist",
        file: "task-checklist.md",
        template: "task-checklist",
        produced_at: "executing",
        produced_by: "executor",
      }),
    ],
  };
}

const SESSION_DETAIL_EXTRAS = (
  <>
    <Route path="/p/:projectId/sessions" element={<div>sessions stub</div>} />
    <Route path="/p/:projectId/issues/:key" element={<div>issue stub</div>} />
  </>
);

afterEach(() => {
  cleanup();
});

describe("SessionDetail", () => {
  it("renders header, tabs, and switches to each tab", () => {
    const session = fixtureSession();
    const qc = makeTestQueryClient();
    qc.setQueryData(queryKeys.session("p1", session.id), session);
    qc.setQueryData(queryKeys.issue("p1", "KUI-1"), fixtureIssue());
    qc.setQueryData(queryKeys.artifactManifest("p1"), fixtureManifest());
    qc.setQueryData(queryKeys.sessionArtifacts("p1", session.id), []);

    const { container } = renderWithProviders(<SessionDetail />, {
      queryClient: qc,
      initialPath: `/p/p1/sessions/${session.id}`,
      routePath: "/p/:projectId/sessions/:sid",
      extraRoutes: SESSION_DETAIL_EXTRAS,
    });

    expect(screen.getByText("Foundation packaging")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("1/3")).toBeInTheDocument();

    // Plan tab active by default, markdown rendered
    expect(container.querySelector('[role="tabpanel"][data-state="active"]')).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Plan" })).toBeInTheDocument();

    // Issues tab
    clickTab(screen.getByRole("tab", { name: "Issues" }));
    expect(screen.getByText(/Grouped because/)).toBeInTheDocument();
    expect(screen.getByText("First issue")).toBeInTheDocument();

    // Repos tab
    clickTab(screen.getByRole("tab", { name: "Repos" }));
    expect(screen.getByText("SeidoAI/tripwire")).toBeInTheDocument();

    // Artifacts tab — verify the inner ArtifactList tabs appear
    clickTab(screen.getByRole("tab", { name: "Artifacts" }));
    expect(container.querySelector('[data-tab-name="plan"]')).not.toBeNull();
    expect(container.querySelector('[data-tab-name="task-checklist"]')).not.toBeNull();
  });

  it("resets the active tab to Plan when the URL :sid changes", async () => {
    const sessionA = fixtureSession({ id: "sess-a", name: "Session A" });
    const sessionB = fixtureSession({ id: "sess-b", name: "Session B" });
    const qc = makeTestQueryClient();
    qc.setQueryData(queryKeys.session("p1", sessionA.id), sessionA);
    qc.setQueryData(queryKeys.session("p1", sessionB.id), sessionB);

    // A link inside the route tree triggers a client-side navigation
    // so the `:sid` segment changes while the Router / QueryClient /
    // DOM tree are all preserved — the exact condition the
    // `key={sid}` fix targets.
    const GoToB = () => (
      <Link to={`/p/p1/sessions/${sessionB.id}`} data-testid="nav-b">
        go B
      </Link>
    );

    const { container } = renderWithProviders(
      <>
        <GoToB />
        <SessionDetail />
      </>,
      {
        queryClient: qc,
        initialPath: `/p/p1/sessions/${sessionA.id}`,
        routePath: "/p/:projectId/sessions/:sid",
        extraRoutes: <Route path="/p/:projectId/sessions" element={<div>sessions stub</div>} />,
      },
    );

    // Start on Session A, switch to Repos tab.
    expect(screen.getByText("Session A")).toBeInTheDocument();
    clickTab(screen.getByRole("tab", { name: "Repos" }));
    const activeA = container.querySelector('[role="tab"][data-state="active"]');
    expect(activeA?.textContent).toMatch(/Repos/);

    // Client-side nav to session B via an in-tree link.
    fireEvent.click(screen.getByTestId("nav-b"));

    // React re-renders with the new :sid. `key={sid}` on
    // SessionDetailInner remounts the subtree; the uncontrolled Tabs
    // default ("plan") wins.
    expect(await screen.findByText("Session B")).toBeInTheDocument();
    const activeB = container.querySelector('[role="tab"][data-state="active"]');
    expect(activeB?.textContent).toMatch(/Plan/);
  });

  it("renders 'not found' when the session API returns 404", async () => {
    server.use(
      http.get("/api/projects/p1/sessions/missing", () =>
        HttpResponse.json({ detail: "missing", code: "session/not_found" }, { status: 404 }),
      ),
    );
    renderWithProviders(<SessionDetail />, {
      initialPath: "/p/p1/sessions/missing",
      routePath: "/p/:projectId/sessions/:sid",
      extraRoutes: <Route path="/p/:projectId/sessions" element={<div>sessions stub</div>} />,
    });

    expect(await screen.findByText("Session not found")).toBeInTheDocument();
  });
});
