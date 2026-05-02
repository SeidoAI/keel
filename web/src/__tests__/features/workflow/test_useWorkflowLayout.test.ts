import { describe, expect, it } from "vitest";

import { buildWorkflowTerritory } from "@/features/workflow/useWorkflowLayout";
import type { WorkflowGraph, WorkflowStatus } from "@/lib/api/endpoints/workflow";

function buildGraph(overrides: Partial<WorkflowGraph> = {}): WorkflowGraph {
  return {
    project_id: "p1",
    workflows: [
      {
        id: "coding-session",
        actor: "coding-agent",
        trigger: "session.spawn",
        statuses: [
          {
            id: "queued",
            next: { kind: "single", single: "executing" },
            validators: [],
            jit_prompts: [],
            prompt_checks: [],
            artifacts: { consumes: [], produces: [{ id: "plan", label: "plan.md" }] },
          },
          {
            id: "executing",
            next: {
              kind: "conditional",
              branches: [
                // biome-ignore lint/suspicious/noThenProperty: mirrors workflow.yaml branch syntax.
                { if: "review.outcome == approved", then: "in_review" },
                { else: "queued" },
              ],
            },
            validators: [],
            jit_prompts: [],
            prompt_checks: [],
            artifacts: { consumes: [], produces: [{ id: "diff", label: "diff" }] },
          },
          {
            id: "in_review",
            next: { kind: "terminal" },
            validators: [],
            jit_prompts: [],
            prompt_checks: [],
            artifacts: { consumes: [], produces: [] },
          },
        ],
        routes: [
          {
            id: "queued-to-executing",
            workflow_id: "coding-session",
            actor: "pm-agent",
            from: "queued",
            to: "executing",
            kind: "forward",
            label: "spawn",
            trigger: "command.pm-session-spawn",
            command: "pm-session-spawn",
            controls: {
              validators: ["v_check", "v_check"],
              jit_prompts: [],
              prompt_checks: ["pm-session-review"],
            },
            skills: ["project-manager"],
            emits: { artifacts: [], events: [], comments: [], status_changes: [] },
          },
          {
            id: "executing-to-review",
            workflow_id: "coding-session",
            actor: "coding-agent",
            from: "executing",
            to: "in_review",
            kind: "forward",
            label: "submit",
            trigger: "session.complete",
            command: null,
            controls: {
              validators: [],
              jit_prompts: ["self-review"],
              prompt_checks: [],
            },
            skills: ["backend-development"],
            emits: {
              artifacts: [{ id: "diff", label: "diff" }],
              events: [],
              comments: [],
              status_changes: [],
            },
          },
          {
            id: "review-return",
            workflow_id: "coding-session",
            actor: "pm-agent",
            from: "in_review",
            to: "executing",
            kind: "return",
            label: "request changes",
            trigger: "review.outcome == changes_requested",
            command: "pm-session-review",
            controls: { validators: [], jit_prompts: [], prompt_checks: [] },
            skills: ["verification"],
            emits: { artifacts: [], events: [], comments: ["changes"], status_changes: [] },
          },
          {
            id: "review-sink",
            workflow_id: "coding-session",
            actor: "code",
            from: "in_review",
            to: "sink:merged",
            kind: "terminal",
            label: "merge",
            trigger: "pr.merge",
            command: null,
            controls: { validators: [], jit_prompts: [], prompt_checks: [] },
            skills: [],
            emits: { artifacts: [], events: ["pr.merged"], comments: [], status_changes: [] },
          },
        ],
      },
    ],
    registry: {
      validators: [{ id: "v_check", label: "check", blocking: true }],
      jit_prompts: [{ id: "self-review", label: "self review", blocking: true }],
      prompt_checks: [{ id: "pm-session-review", label: "session review", blocking: true }],
      commands: [
        { id: "pm-session-spawn", label: "session spawn", blocking: false },
        { id: "pm-session-review", label: "session review", blocking: false },
      ],
      skills: [
        { id: "project-manager", label: "project manager", blocking: false },
        { id: "backend-development", label: "backend development", blocking: false },
        { id: "verification", label: "verification", blocking: false },
      ],
    },
    drift: {
      count: 1,
      findings: [
        {
          source: "definition",
          code: "workflow/unknown_route_status",
          workflow: "coding-session",
          status: "executing",
          severity: "error",
          message: "bad route",
        },
      ],
    },
    ...overrides,
  };
}

describe("buildWorkflowTerritory", () => {
  it("uses statuses as the shaded territory units", () => {
    const territory = buildWorkflowTerritory(buildGraph());

    expect(territory?.statuses.map((region) => region.status.id)).toEqual([
      "queued",
      "executing",
      "in_review",
    ]);
  });

  it("uses explicit workflow routes as the foreground process flow", () => {
    const territory = buildWorkflowTerritory(buildGraph());

    expect(territory?.routes.map((route) => [route.id, route.source, route.target])).toEqual([
      ["queued-to-executing", "queued", "executing"],
      ["executing-to-review", "executing", "in_review"],
      ["review-return", "in_review", "executing"],
      ["review-sink", "in_review", "sink:merged"],
    ]);
  });

  it("groups validators and prompt checks into route gate clusters", () => {
    const territory = buildWorkflowTerritory(buildGraph());
    const route = territory?.routes.find((item) => item.id === "queued-to-executing");

    expect(route?.gate?.validators).toHaveLength(2);
    expect(route?.gate?.promptChecks).toHaveLength(1);
    expect(route?.gate?.id).toBe("queued-to-executing:gate");
  });

  it("keeps JIT prompts as intervention markers, not gate members", () => {
    const territory = buildWorkflowTerritory(buildGraph());
    const route = territory?.routes.find((item) => item.id === "executing-to-review");

    expect(route?.jitPrompts).toHaveLength(1);
    expect(route?.gate?.validators.map((entry) => entry.id) ?? []).not.toContain("self-review");
  });

  it("derives artifacts from status and route declarations", () => {
    const territory = buildWorkflowTerritory(buildGraph());
    const queued = territory?.statuses.find((region) => region.status.id === "queued");
    const route = territory?.routes.find((item) => item.id === "executing-to-review");

    expect(queued?.artifacts).toContainEqual({
      id: "queued:produces:plan",
      statusId: "queued",
      direction: "produces",
      artifact: { id: "plan", label: "plan.md" },
    });
    expect(route?.artifacts).toEqual([
      {
        id: "executing-to-review:emits:diff",
        routeId: "executing-to-review",
        statusId: "in_review",
        direction: "emits",
        artifact: { id: "diff", label: "diff" },
      },
    ]);
  });

  it("classifies forward, return, and terminal route geometry", () => {
    const territory = buildWorkflowTerritory(buildGraph());

    expect(territory?.routes.map((route) => [route.id, route.kind])).toEqual([
      ["queued-to-executing", "forward"],
      ["executing-to-review", "forward"],
      ["review-return", "return"],
      ["review-sink", "terminal"],
    ]);
  });

  it("uses static complexity to widen more detailed statuses within bounds", () => {
    const territory = buildWorkflowTerritory(buildGraph());
    const queued = territory?.statuses.find((region) => region.status.id === "queued");
    const executing = territory?.statuses.find((region) => region.status.id === "executing");

    expect(executing?.complexity).toBeGreaterThan(0);
    expect(executing?.width).toBeGreaterThanOrEqual(queued?.width ?? 0);
    expect(executing?.width).toBeLessThanOrEqual(320);
  });

  it("attaches drift findings to their status region", () => {
    const territory = buildWorkflowTerritory(buildGraph());
    const executing = territory?.statuses.find((region) => region.status.id === "executing");

    expect(executing?.drift).toHaveLength(1);
    expect(executing?.drift[0]?.code).toBe("workflow/unknown_route_status");
  });

  it("does not crash when a runtime payload is missing registry or drift", () => {
    const { registry: _registry, drift: _drift, ...graph } = buildGraph();

    const territory = buildWorkflowTerritory(graph as WorkflowGraph);
    const route = territory?.routes.find((item) => item.id === "queued-to-executing");

    expect(route?.gate?.validators.map((entry) => entry.id)).toEqual(["v_check", "v_check"]);
    expect(territory?.drift).toEqual([]);
  });

  it("does not crash when a status omits optional collection fields", () => {
    const graph = buildGraph();
    const workflow = graph.workflows[0];
    if (!workflow) throw new Error("missing workflow fixture");
    const executing = workflow.statuses[1] as Partial<WorkflowStatus>;
    delete executing.validators;
    delete executing.prompt_checks;
    delete executing.jit_prompts;
    delete executing.artifacts;

    const territory = buildWorkflowTerritory(graph);
    const region = territory?.statuses.find((item) => item.status.id === "executing");

    expect(region?.artifacts).toEqual([]);
  });
});
