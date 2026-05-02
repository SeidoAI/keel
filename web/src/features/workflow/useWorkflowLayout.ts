import { useMemo } from "react";

import type {
  WorkflowArtifactRef,
  WorkflowDefinition,
  WorkflowDriftFinding,
  WorkflowGraph,
  WorkflowRegistryEntry,
  WorkflowRoute,
  WorkflowRouteControls,
  WorkflowStatus,
} from "@/lib/api/endpoints/workflow";

export type RouteKind = "forward" | "return" | "loop" | "side" | "terminal";
export type RouteActor = "pm-agent" | "coding-agent" | "code" | string;

export interface GateCluster {
  id: string;
  routeId: string;
  statusId: string;
  validators: WorkflowRegistryEntry[];
  promptChecks: WorkflowRegistryEntry[];
  blocking: boolean;
}

export interface JitPromptMarker {
  id: string;
  routeId: string;
  statusId: string;
  prompt: WorkflowRegistryEntry;
}

export interface CommandMarker {
  id: string;
  routeId: string;
  command: WorkflowRegistryEntry;
}

export interface SkillMarker {
  id: string;
  routeId: string;
  skill: WorkflowRegistryEntry;
}

export interface ArtifactMarker {
  id: string;
  routeId?: string;
  statusId: string;
  direction: "produces" | "consumes" | "emits";
  artifact: WorkflowArtifactRef;
}

export interface ProcessRoute {
  id: string;
  source: string;
  target: string;
  actor: RouteActor;
  kind: RouteKind;
  label: string;
  trigger?: string | null;
  command?: CommandMarker;
  skills: SkillMarker[];
  gate: GateCluster | null;
  jitPrompts: JitPromptMarker[];
  artifacts: ArtifactMarker[];
  fromX: number;
  toX: number;
  y: number;
  path: string;
}

export interface TerritoryStatus {
  status: WorkflowStatus;
  index: number;
  complexity: number;
  width: number;
  x: number;
  incoming: number;
  outgoing: number;
  artifacts: ArtifactMarker[];
  drift: WorkflowDriftFinding[];
}

export interface WorkflowTerritory {
  workflow: WorkflowDefinition;
  statuses: TerritoryStatus[];
  routes: ProcessRoute[];
  drift: WorkflowDriftFinding[];
  canvasWidth: number;
  canvasHeight: number;
}

const MIN_STATUS_WIDTH = 180;
const MAX_STATUS_WIDTH = 320;
const STATUS_GAP = 28;
const CANVAS_PADDING_X = 56;
const CANVAS_HEIGHT = 540;
const ACTOR_LANES: Record<string, number> = {
  "pm-agent": 82,
  "coding-agent": 178,
  code: 274,
};

export function buildWorkflowTerritory(
  graph: WorkflowGraph,
  workflowId?: string,
): WorkflowTerritory | null {
  const workflows = graph.workflows ?? [];
  const workflow =
    (workflowId ? workflows.find((wf) => wf.id === workflowId) : workflows[0]) ?? null;
  if (!workflow) return null;

  const registry = withRegistryDefaults(graph.registry);
  const driftFindings = graph.drift?.findings ?? [];
  const statuses = workflow.statuses ?? [];
  const statusIndex = new Map(statuses.map((status, index) => [status.id, index]));
  const explicitRoutes = workflow.routes ?? [];
  const routes = explicitRoutes.length > 0 ? explicitRoutes : synthesizeRoutes(workflow);
  const incoming = countBy(routes.map((route) => route.to).filter((ref) => statusIndex.has(ref)));
  const outgoing = countBy(routes.map((route) => route.from).filter((ref) => statusIndex.has(ref)));
  const driftByStatus = groupDrift(driftFindings, workflow.id);
  const statusWidths = statuses.map((status) =>
    widthForStatus(status, routes, incoming.get(status.id) ?? 0, outgoing.get(status.id) ?? 0),
  );

  let cursor = CANVAS_PADDING_X;
  const territoryStatuses: TerritoryStatus[] = statuses.map((status, index) => {
    const width = statusWidths[index] ?? MIN_STATUS_WIDTH;
    const statusRoutes = routes.filter(
      (route) => route.from === status.id || route.to === status.id,
    );
    const routeArtifacts = routes
      .filter((route) => route.to === status.id)
      .flatMap((route) =>
        (route.emits?.artifacts ?? []).map((artifact) => ({
          id: `${route.id}:emits:${artifact.id}`,
          routeId: route.id,
          statusId: status.id,
          direction: "emits" as const,
          artifact,
        })),
      );
    const statusArtifacts = [
      ...((status.artifacts?.produces ?? []).map((artifact) => ({
        id: `${status.id}:produces:${artifact.id}`,
        statusId: status.id,
        direction: "produces" as const,
        artifact,
      })) satisfies ArtifactMarker[]),
      ...((status.artifacts?.consumes ?? []).map((artifact) => ({
        id: `${status.id}:consumes:${artifact.id}`,
        statusId: status.id,
        direction: "consumes" as const,
        artifact,
      })) satisfies ArtifactMarker[]),
      ...routeArtifacts,
    ];
    const complexity =
      statusRoutes.length +
      (incoming.get(status.id) ?? 0) +
      (outgoing.get(status.id) ?? 0) +
      statusArtifacts.length +
      (status.validators?.length ?? 0) +
      (status.prompt_checks?.length ?? 0) +
      (status.jit_prompts?.length ?? 0);
    const region = {
      status,
      index,
      complexity,
      width,
      x: cursor,
      incoming: incoming.get(status.id) ?? 0,
      outgoing: outgoing.get(status.id) ?? 0,
      artifacts: statusArtifacts,
      drift: driftByStatus.get(status.id) ?? [],
    };
    cursor += width + STATUS_GAP;
    return region;
  });

  const statusCenters = new Map(
    territoryStatuses.map((region) => [region.status.id, region.x + region.width / 2]),
  );
  const canvasWidth = Math.max(cursor + CANVAS_PADDING_X - STATUS_GAP, 860);
  const routeModels = routes.map((route, index) =>
    buildProcessRoute(route, {
      index,
      canvasWidth,
      statusCenters,
      statusIndex,
      registry,
    }),
  );

  return {
    workflow,
    statuses: territoryStatuses,
    routes: routeModels,
    drift: driftFindings,
    canvasWidth,
    canvasHeight: CANVAS_HEIGHT,
  };
}

function withRegistryDefaults(registry: WorkflowGraph["registry"] | undefined) {
  return {
    validators: registry?.validators ?? [],
    jit_prompts: registry?.jit_prompts ?? [],
    prompt_checks: registry?.prompt_checks ?? [],
    commands: registry?.commands ?? [],
    skills: registry?.skills ?? [],
  };
}

function buildProcessRoute(
  route: WorkflowRoute,
  ctx: {
    index: number;
    canvasWidth: number;
    statusCenters: Map<string, number>;
    statusIndex: Map<string, number>;
    registry: ReturnType<typeof withRegistryDefaults>;
  },
): ProcessRoute {
  const fromX = xForRef(route.from, ctx.statusCenters, ctx.canvasWidth);
  const toX = xForRef(route.to, ctx.statusCenters, ctx.canvasWidth);
  const lane = laneForActor(route.actor, ctx.index);
  const kind = normalizeKind(route.kind, route.from, route.to, ctx.statusIndex);
  const controls = route.controls ?? emptyControls();
  const statusId = ctx.statusIndex.has(route.to)
    ? route.to
    : ctx.statusIndex.has(route.from)
      ? route.from
      : route.to;
  const validatorsById = byId(ctx.registry.validators);
  const promptChecksById = byId(ctx.registry.prompt_checks);
  const promptsById = byId(ctx.registry.jit_prompts);
  const commandsById = byId(ctx.registry.commands);
  const skillsById = byId(ctx.registry.skills);
  const gate = buildGateCluster(route.id, statusId, controls, validatorsById, promptChecksById);
  const jitPrompts = (controls.jit_prompts ?? []).map((id) => ({
    id: `${route.id}:jit:${id}`,
    routeId: route.id,
    statusId,
    prompt: entryForRoute(promptsById, id, route.id),
  }));
  const command = route.command
    ? {
        id: `${route.id}:command:${route.command}`,
        routeId: route.id,
        command: entryForRoute(commandsById, route.command, route.id),
      }
    : undefined;
  const skills = (route.skills ?? []).map((id) => ({
    id: `${route.id}:skill:${id}`,
    routeId: route.id,
    skill: entryForRoute(skillsById, id, route.id),
  }));
  const artifacts = (route.emits?.artifacts ?? []).map((artifact) => ({
    id: `${route.id}:emits:${artifact.id}`,
    routeId: route.id,
    statusId,
    direction: "emits" as const,
    artifact,
  }));

  return {
    id: route.id,
    source: route.from,
    target: route.to,
    actor: route.actor,
    kind,
    label: route.label || route.command || route.id,
    trigger: route.trigger,
    command,
    skills,
    gate,
    jitPrompts,
    artifacts,
    fromX,
    toX,
    y: lane,
    path: pathForRoute(kind, fromX, toX, lane),
  };
}

function xForRef(ref: string, centers: Map<string, number>, canvasWidth: number): number {
  if (ref.startsWith("source:")) return 24;
  if (ref.startsWith("sink:")) return canvasWidth - 24;
  return centers.get(ref) ?? canvasWidth / 2;
}

function laneForActor(actor: string, index: number): number {
  const base = ACTOR_LANES[actor] ?? ACTOR_LANES.code;
  return (base ?? 274) + (index % 3) * 10;
}

function pathForRoute(kind: RouteKind, fromX: number, toX: number, y: number): string {
  const mid = (fromX + toX) / 2;
  if (kind === "return" || toX < fromX) {
    const lift = Math.max(46, Math.min(86, Math.abs(fromX - toX) / 4));
    return `M ${fromX} ${y} C ${fromX} ${y - lift}, ${toX} ${y - lift}, ${toX} ${y}`;
  }
  if (kind === "loop") {
    return `M ${fromX} ${y} C ${fromX - 48} ${y - 70}, ${fromX + 48} ${y - 70}, ${fromX} ${y}`;
  }
  if (kind === "side") {
    return `M ${fromX} ${y} C ${mid} ${y + 34}, ${mid} ${y + 34}, ${toX} ${y}`;
  }
  return `M ${fromX} ${y} C ${mid} ${y}, ${mid} ${y}, ${toX} ${y}`;
}

function buildGateCluster(
  routeId: string,
  statusId: string,
  controls: WorkflowRouteControls,
  validatorsById: Map<string, WorkflowRegistryEntry>,
  promptChecksById: Map<string, WorkflowRegistryEntry>,
): GateCluster | null {
  const validators = (controls.validators ?? []).map((id) =>
    entryForRoute(validatorsById, id, routeId),
  );
  const promptChecks = (controls.prompt_checks ?? []).map((id) =>
    entryForRoute(promptChecksById, id, routeId),
  );
  if (validators.length === 0 && promptChecks.length === 0) return null;
  return {
    id: `${routeId}:gate`,
    routeId,
    statusId,
    validators,
    promptChecks,
    blocking: [...validators, ...promptChecks].some((entry) => entry.blocking !== false),
  };
}

function widthForStatus(
  status: WorkflowStatus,
  routes: WorkflowRoute[],
  incoming: number,
  outgoing: number,
): number {
  const routePressure = routes.filter(
    (route) => route.from === status.id || route.to === status.id,
  ).length;
  const artifactPressure =
    (status.artifacts?.produces?.length ?? 0) + (status.artifacts?.consumes?.length ?? 0);
  const controlPressure =
    (status.validators?.length ?? 0) +
    (status.prompt_checks?.length ?? 0) +
    (status.jit_prompts?.length ?? 0);
  return clamp(
    MIN_STATUS_WIDTH +
      (routePressure + artifactPressure + controlPressure + incoming + outgoing) * 14,
    MIN_STATUS_WIDTH,
    MAX_STATUS_WIDTH,
  );
}

function synthesizeRoutes(workflow: WorkflowDefinition): WorkflowRoute[] {
  const statusIndex = new Map((workflow.statuses ?? []).map((status, index) => [status.id, index]));
  const routes: WorkflowRoute[] = [];
  for (const status of workflow.statuses ?? []) {
    const next = status.next ?? ({ kind: "terminal" } as const);
    if (next.kind === "terminal") {
      routes.push(synthesizedRoute(workflow, status, `sink:${status.id}`, "terminal"));
    } else if (next.kind === "single") {
      routes.push(
        synthesizedRoute(
          workflow,
          status,
          next.single,
          normalizeKind("", status.id, next.single, statusIndex),
        ),
      );
    } else {
      for (const branch of next.branches) {
        const target = "else" in branch ? branch.else : branch.then;
        const label = "else" in branch ? "else" : branch.if;
        routes.push({
          ...synthesizedRoute(
            workflow,
            status,
            target,
            normalizeKind("", status.id, target, statusIndex),
          ),
          id: `${status.id}:branch:${label}:${target}`,
          label,
        });
      }
    }
  }
  return routes;
}

function synthesizedRoute(
  workflow: WorkflowDefinition,
  status: WorkflowStatus,
  target: string,
  kind: RouteKind,
): WorkflowRoute {
  return {
    id: `${status.id}:to:${target}`,
    workflow_id: workflow.id,
    actor: workflow.actor || "code",
    from: status.id,
    to: target,
    kind,
    label: target,
    trigger: null,
    command: null,
    controls: {
      validators: status.validators ?? [],
      jit_prompts: status.jit_prompts ?? [],
      prompt_checks: status.prompt_checks ?? [],
    },
    skills: [],
    emits: {
      artifacts: [],
      events: [],
      comments: [],
      status_changes: [],
    },
  };
}

function normalizeKind(
  kind: string | undefined,
  from: string,
  to: string,
  statusIndex: Map<string, number>,
): RouteKind {
  if (
    kind === "forward" ||
    kind === "return" ||
    kind === "loop" ||
    kind === "side" ||
    kind === "terminal"
  ) {
    return kind;
  }
  if (to.startsWith("sink:")) return "terminal";
  if (from === to) return "loop";
  const fromIndex = statusIndex.get(from);
  const toIndex = statusIndex.get(to);
  if (fromIndex === undefined || toIndex === undefined) return "side";
  if (toIndex > fromIndex) return "forward";
  if (toIndex < fromIndex) return "return";
  return "side";
}

function emptyControls(): WorkflowRouteControls {
  return { validators: [], jit_prompts: [], prompt_checks: [] };
}

function byId(entries: WorkflowRegistryEntry[]): Map<string, WorkflowRegistryEntry> {
  return new Map(entries.map((entry) => [entry.id, entry]));
}

function entryForRoute(
  entries: Map<string, WorkflowRegistryEntry>,
  id: string,
  routeId: string,
): WorkflowRegistryEntry {
  return { ...(entries.get(id) ?? fallbackEntry(id)), route: routeId };
}

function fallbackEntry(id: string): WorkflowRegistryEntry {
  return { id, label: id };
}

function countBy(values: string[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
  return counts;
}

function groupDrift(
  findings: WorkflowDriftFinding[],
  workflowId: string,
): Map<string, WorkflowDriftFinding[]> {
  const grouped = new Map<string, WorkflowDriftFinding[]>();
  for (const finding of findings) {
    if (finding.workflow !== workflowId || !finding.status) continue;
    const bucket = grouped.get(finding.status) ?? [];
    bucket.push(finding);
    grouped.set(finding.status, bucket);
  }
  return grouped;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function useWorkflowTerritory(
  graph: WorkflowGraph | undefined,
  workflowId?: string,
): WorkflowTerritory | null {
  return useMemo(
    () => (graph ? buildWorkflowTerritory(graph, workflowId) : null),
    [graph, workflowId],
  );
}
