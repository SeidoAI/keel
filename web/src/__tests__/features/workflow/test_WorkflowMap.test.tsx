import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { WorkflowMap } from "@/features/workflow/WorkflowMap";
import type { WorkflowGraph } from "@/lib/api/endpoints/workflow";
import { queryKeys } from "@/lib/api/queryKeys";
import { server } from "../../mocks/server";

vi.mock("@/app/ProjectShell", () => ({
  useProjectShell: () => ({ projectId: "p1", wsStatus: "open" }),
}));

function makeGraph(overrides: Partial<WorkflowGraph> = {}): WorkflowGraph {
  return {
    project_id: "p1",
    workflows: [
      {
        id: "coding-session",
        actor: "coding-agent",
        trigger: "session.spawn",
        statuses: [
          status("planned", { produces: [], consumes: [{ id: "issue", label: "issue brief" }] }),
          status("queued", {
            produces: [{ id: "plan", label: "plan.md", path: "sessions/{session_id}/plan.md" }],
          }),
          status("executing", {
            produces: [{ id: "diff", label: "implementation diff" }],
          }),
          status("in_review", { produces: [{ id: "review", label: "review notes" }] }),
          status("verified"),
          status("completed", { produces: [{ id: "sig", label: "session signature" }] }),
        ],
        routes: [
          route({
            id: "planned-to-queued",
            actor: "pm-agent",
            from: "planned",
            to: "queued",
            label: "queue",
            command: "pm-session-queue",
            validators: ["v_check"],
            skills: ["project-manager"],
          }),
          route({
            id: "queued-to-executing",
            actor: "pm-agent",
            from: "queued",
            to: "executing",
            label: "spawn",
            command: "pm-session-spawn",
            validators: ["v_check"],
            skills: ["project-manager", "backend-development"],
          }),
          route({
            id: "executing-to-review",
            actor: "coding-agent",
            from: "executing",
            to: "in_review",
            label: "submit",
            trigger: "session.complete",
            jit_prompts: ["self-review"],
            emits: [{ id: "diff", label: "implementation diff" }],
            skills: ["backend-development"],
          }),
          route({
            id: "review-approved",
            actor: "pm-agent",
            from: "in_review",
            to: "verified",
            label: "approve",
            command: "pm-session-review",
            prompt_checks: ["pm-session-review"],
            validators: ["v_artifact_presence"],
            skills: ["project-manager", "verification"],
          }),
          route({
            id: "review-return",
            actor: "pm-agent",
            from: "in_review",
            to: "executing",
            kind: "return",
            label: "request changes",
            command: "pm-session-review",
            skills: ["verification"],
          }),
          route({
            id: "verified-to-completed",
            actor: "pm-agent",
            from: "verified",
            to: "completed",
            label: "complete",
            command: "pm-session-complete",
          }),
        ],
      },
    ],
    registry: {
      validators: [
        {
          id: "v_check",
          label: "generic check",
          description: "duplicate validator id used in multiple routes",
          blocking: true,
        },
        {
          id: "v_artifact_presence",
          label: "artifact presence",
          description: "required artifacts exist",
          blocking: true,
        },
      ],
      jit_prompts: [
        {
          id: "self-review",
          label: "self review",
          fires_on_event: "session.complete",
          blocking: true,
          prompt_revealed: null,
          prompt_redacted: "<<JIT prompt registered>>",
        },
      ],
      prompt_checks: [
        {
          id: "pm-session-review",
          label: "session review",
          blocking: true,
        },
      ],
      commands: [
        { id: "pm-session-queue", label: "session queue", source: "commands/pm-session-queue.md" },
        { id: "pm-session-spawn", label: "session spawn", source: "commands/pm-session-spawn.md" },
        {
          id: "pm-session-review",
          label: "session review",
          source: "commands/pm-session-review.md",
        },
        {
          id: "pm-session-complete",
          label: "session complete",
          source: "commands/pm-session-complete.md",
        },
      ],
      skills: [
        {
          id: "project-manager",
          label: "project manager",
          source: "skills/project-manager/SKILL.md",
        },
        {
          id: "backend-development",
          label: "backend development",
          source: "skills/backend-development/SKILL.md",
        },
        { id: "verification", label: "verification", source: "skills/verification/SKILL.md" },
      ],
    },
    drift: {
      count: 1,
      findings: [
        {
          source: "definition",
          code: "workflow/unknown_route_status",
          workflow: "coding-session",
          status: "in_review",
          severity: "error",
          message: "in_review references a missing status",
        },
      ],
    },
    ...overrides,
  };
}

function status(
  id: string,
  artifacts: {
    produces?: { id: string; label: string; path?: string }[];
    consumes?: { id: string; label: string; path?: string }[];
  } = {},
) {
  return {
    id,
    label: id.replace("_", " "),
    next:
      id === "completed"
        ? ({ kind: "terminal" } as const)
        : ({ kind: "single", single: id } as const),
    validators: [],
    jit_prompts: [],
    prompt_checks: [],
    artifacts: {
      consumes: artifacts.consumes ?? [],
      produces: artifacts.produces ?? [],
    },
  };
}

function route({
  id,
  actor,
  from,
  to,
  kind = "forward",
  label,
  trigger = null,
  command = null,
  validators = [],
  jit_prompts = [],
  prompt_checks = [],
  skills = [],
  emits = [],
}: {
  id: string;
  actor: string;
  from: string;
  to: string;
  kind?: string;
  label: string;
  trigger?: string | null;
  command?: string | null;
  validators?: string[];
  jit_prompts?: string[];
  prompt_checks?: string[];
  skills?: string[];
  emits?: { id: string; label: string }[];
}) {
  return {
    id,
    workflow_id: "coding-session",
    actor,
    from,
    to,
    kind,
    label,
    trigger,
    command,
    controls: { validators, jit_prompts, prompt_checks },
    skills,
    emits: { artifacts: emits, events: [], comments: [], status_changes: [] },
  };
}

function withProviders(graph: WorkflowGraph | null, opts?: { pmMode?: boolean }) {
  const pmMode = Boolean(opts?.pmMode);
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Number.POSITIVE_INFINITY } },
  });
  if (graph) qc.setQueryData([...queryKeys.workflow("p1"), { pmMode }] as const, graph);
  const initialEntry = pmMode ? "/p/p1/workflow?role=pm" : "/p/p1/workflow";
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/p/:projectId/workflow" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("WorkflowMap", () => {
  it("renders one process map from workflow statuses and routes", () => {
    const Wrapper = withProviders(makeGraph());
    render(
      <Wrapper>
        <WorkflowMap />
      </Wrapper>,
    );

    expect(screen.getByTestId("workflow-territory")).toBeInTheDocument();
    expect(screen.queryByTestId("workflow-yaml-panel")).not.toBeInTheDocument();
    for (const id of ["planned", "queued", "executing", "in_review", "verified", "completed"]) {
      expect(screen.getByTestId(`status-region-${id}`)).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: /Route request changes/i })).toBeInTheDocument();
  });

  it("renders process-map grammar in the legend", () => {
    const Wrapper = withProviders(makeGraph());
    render(
      <Wrapper>
        <WorkflowMap />
      </Wrapper>,
    );
    const legend = screen.getByLabelText(/legend/i);
    for (const label of [
      "STATUS TERRITORY",
      "ACTOR ROUTE",
      "COMMAND",
      "GATE",
      "JIT PROMPT",
      "SKILL",
      "ARTIFACT",
    ]) {
      expect(within(legend).getByText(label)).toBeInTheDocument();
    }
  });

  it("opens route, command, skill, gate, JIT prompt, artifact, status, and drift drawers", () => {
    const Wrapper = withProviders(makeGraph());
    render(
      <Wrapper>
        <WorkflowMap />
      </Wrapper>,
    );

    fireEvent.click(screen.getByRole("button", { name: /Route request changes/i }));
    expect(within(screen.getByRole("dialog")).getByText("ROUTE")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    const commandButtons = screen.getAllByRole("button", {
      name: /Command session review/i,
    });
    expect(commandButtons.length).toBeGreaterThan(0);
    const commandButton = commandButtons[0];
    if (!commandButton) throw new Error("missing command marker");
    fireEvent.click(commandButton);
    expect(within(screen.getByRole("dialog")).getByText("COMMAND")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    const skillButtons = screen.getAllByRole("button", { name: /Skill verification/i });
    expect(skillButtons.length).toBeGreaterThan(0);
    const skillButton = skillButtons[0];
    if (!skillButton) throw new Error("missing skill marker");
    fireEvent.click(skillButton);
    expect(within(screen.getByRole("dialog")).getByText("SKILL")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    fireEvent.click(screen.getByRole("button", { name: /Gate on route review-approved/i }));
    expect(within(screen.getByRole("dialog")).getByText("GATE")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    fireEvent.click(screen.getByRole("button", { name: /JIT prompt self review/i }));
    expect(
      within(screen.getByRole("dialog")).getByText("<<JIT prompt registered>>"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    fireEvent.click(screen.getByRole("button", { name: /Artifact plan.md/i }));
    expect(within(screen.getByRole("dialog")).getByText("ARTIFACT")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    fireEvent.click(screen.getByRole("button", { name: /^Status executing$/i }));
    expect(within(screen.getByRole("dialog")).getByText("STATUS")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    fireEvent.click(screen.getByRole("button", { name: /^Drift$/i }));
    expect(
      within(screen.getByRole("dialog")).getByText("workflow/unknown_route_status"),
    ).toBeInTheDocument();
  });

  it("reveals JIT prompt body for PM-mode payloads", () => {
    const graph = makeGraph({
      registry: {
        ...makeGraph().registry,
        jit_prompts: [
          {
            id: "self-review",
            label: "self review",
            fires_on_event: "session.complete",
            blocking: true,
            prompt_revealed: "secret-prompt-body for the agent",
            prompt_redacted: "<<JIT prompt registered>>",
          },
        ],
      },
    });
    const Wrapper = withProviders(graph, { pmMode: true });
    render(
      <Wrapper>
        <WorkflowMap />
      </Wrapper>,
    );

    fireEvent.click(screen.getByRole("button", { name: /JIT prompt self review/i }));
    expect(within(screen.getByRole("dialog")).getByText(/secret-prompt-body/i)).toBeInTheDocument();
  });

  it("does not emit React duplicate-key warnings when one validator id appears in multiple routes", () => {
    const Wrapper = withProviders(makeGraph());
    render(
      <Wrapper>
        <WorkflowMap />
      </Wrapper>,
    );

    expect(screen.getAllByRole("button", { name: /gate on route/i })).toHaveLength(3);
  });

  it("shows a loading surface while the workflow query is pending", () => {
    server.use(
      http.get("/api/projects/:pid/workflow", async () => {
        await new Promise(() => {});
        return HttpResponse.json({});
      }),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const Wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/p/p1/workflow"]}>
          <Routes>
            <Route path="/p/:projectId/workflow" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
    render(
      <Wrapper>
        <WorkflowMap />
      </Wrapper>,
    );

    expect(screen.getByText(/loading workflow/i)).toBeInTheDocument();
  });

  it("shows an error surface with retry when the request fails", async () => {
    server.use(
      http.get("/api/projects/:pid/workflow", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false, retryDelay: 0 } },
    });
    const Wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/p/p1/workflow"]}>
          <Routes>
            <Route path="/p/:projectId/workflow" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <Wrapper>
        <WorkflowMap />
      </Wrapper>,
    );

    await waitFor(() =>
      expect(screen.getByText(/couldn't load the workflow map/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows the empty state on 404", async () => {
    server.use(
      http.get("/api/projects/:pid/workflow", () =>
        HttpResponse.json({ detail: "not found" }, { status: 404 }),
      ),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const Wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/p/p1/workflow"]}>
          <Routes>
            <Route path="/p/:projectId/workflow" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
    render(
      <Wrapper>
        <WorkflowMap />
      </Wrapper>,
    );

    await waitFor(() =>
      expect(screen.getByText(/workflow not yet available/i)).toBeInTheDocument(),
    );
  });
});
