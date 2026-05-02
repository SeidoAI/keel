import {
  AlertTriangle,
  BellRing,
  BookOpen,
  FileText,
  GitBranch,
  Play,
  ShieldCheck,
  SquareTerminal,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useProjectShell } from "@/app/ProjectShell";
import { Stamp } from "@/components/ui/stamp";
import { ApiError } from "@/lib/api/client";
import { useWorkflow } from "@/lib/api/endpoints/workflow";
import { isPmMode } from "@/lib/role";
import {
  type ArtifactMarker,
  buildWorkflowTerritory,
  type CommandMarker,
  type GateCluster,
  type JitPromptMarker,
  type ProcessRoute,
  type SkillMarker,
  type TerritoryStatus,
  type WorkflowTerritory,
} from "./useWorkflowLayout";
import { WorkflowDrawer, type WorkflowSelection } from "./WorkflowDrawer";

const STATUS_Y = 150;
const STATUS_HEIGHT = 170;
const EVIDENCE_Y = 366;

export function WorkflowMap() {
  const { projectId } = useProjectShell();
  const [searchParams] = useSearchParams();
  const pmMode = useMemo(() => isPmMode(searchParams.get("role")), [searchParams]);
  const query = useWorkflow(projectId, { pmMode });
  const { data: graph, isPending, isError, error, refetch } = query;
  const [workflowId, setWorkflowId] = useState<string | undefined>();
  const territory = useMemo(
    () => (graph ? buildWorkflowTerritory(graph, workflowId) : null),
    [graph, workflowId],
  );
  const [selection, setSelection] = useState<WorkflowSelection | null>(null);

  const stateBranch: React.ReactNode = (() => {
    if (territory) {
      return (
        <WorkflowProcessMap
          territory={territory}
          workflowIds={graph?.workflows.map((workflow) => workflow.id) ?? []}
          selectedWorkflowId={territory.workflow.id}
          onSelectWorkflow={setWorkflowId}
          onSelect={setSelection}
        />
      );
    }
    if (isPending) return <LoadingState />;
    if (isError && !is404(error)) return <ErrorState onRetry={() => void refetch()} />;
    return <EmptyState />;
  })();

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="font-sans font-semibold text-[28px] text-(--color-ink) leading-tight">
          Workflow
        </h1>
        <p className="font-serif text-[14px] italic text-(--color-ink-2) leading-snug">
          a routed process graph over status territory, controls, skills, and proof.
        </p>
      </header>
      <Legend />
      {stateBranch}
      <WorkflowDrawer selection={selection} pmMode={pmMode} onClose={() => setSelection(null)} />
    </div>
  );
}

function WorkflowProcessMap({
  territory,
  workflowIds,
  selectedWorkflowId,
  onSelectWorkflow,
  onSelect,
}: {
  territory: WorkflowTerritory;
  workflowIds: string[];
  selectedWorkflowId: string;
  onSelectWorkflow: (workflowId: string) => void;
  onSelect: (selection: WorkflowSelection) => void;
}) {
  return (
    <section
      aria-label="Workflow process map"
      data-testid="workflow-territory"
      className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-(--radius-stamp) border border-(--color-edge) bg-(--color-paper-2)"
    >
      <WorkflowToolbar
        territory={territory}
        workflowIds={workflowIds}
        selectedWorkflowId={selectedWorkflowId}
        onSelectWorkflow={onSelectWorkflow}
      />
      <div className="min-h-0 flex-1 overflow-auto">
        <div
          className="relative"
          style={{ width: `${territory.canvasWidth}px`, height: `${territory.canvasHeight}px` }}
        >
          <CompassLabels />
          <StatusLayer statuses={territory.statuses} onSelect={onSelect} />
          <RouteLayer routes={territory.routes} />
          <RouteMarkers routes={territory.routes} onSelect={onSelect} />
          <EvidenceLayer statuses={territory.statuses} onSelect={onSelect} />
        </div>
      </div>
    </section>
  );
}

function WorkflowToolbar({
  territory,
  workflowIds,
  selectedWorkflowId,
  onSelectWorkflow,
}: {
  territory: WorkflowTerritory;
  workflowIds: string[];
  selectedWorkflowId: string;
  onSelectWorkflow: (workflowId: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-(--color-edge) bg-(--color-paper) px-4 py-3">
      <Stamp tone="rule">{territory.workflow.id}</Stamp>
      <span className="font-mono text-[11px] text-(--color-ink-3)">
        actor {territory.workflow.actor || "-"} · trigger {territory.workflow.trigger || "-"}
      </span>
      <span className="ml-auto font-mono text-[11px] text-(--color-ink-3)">
        {territory.statuses.length} statuses · {territory.routes.length} routes
      </span>
      {territory.drift.length > 0 ? (
        <Stamp tone="tripwire">{territory.drift.length} drift</Stamp>
      ) : null}
      {workflowIds.length > 1 ? (
        <fieldset className="flex min-w-0 flex-wrap gap-1">
          <legend className="sr-only">Workflow selector</legend>
          {workflowIds.map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => onSelectWorkflow(id)}
              className="rounded-(--radius-stamp) border border-(--color-edge) px-2 py-1 font-mono text-[10px] uppercase tracking-[0.06em] text-(--color-ink-2) data-[active=true]:border-(--color-ink) data-[active=true]:text-(--color-ink)"
              data-active={id === selectedWorkflowId}
            >
              {id}
            </button>
          ))}
        </fieldset>
      ) : null}
    </div>
  );
}

function CompassLabels() {
  return (
    <div className="absolute left-6 right-6 top-4 grid grid-cols-[112px_1fr_112px] items-center gap-3 font-mono text-[10px] uppercase tracking-[0.08em] text-(--color-ink-3)">
      <span>west / intent</span>
      <div className="flex flex-col items-center gap-1">
        <span>north: controls, commands, skills</span>
        <div className="h-px w-full bg-(--color-edge)" />
      </div>
      <span className="text-right">east / closure</span>
    </div>
  );
}

function StatusLayer({
  statuses,
  onSelect,
}: {
  statuses: TerritoryStatus[];
  onSelect: (selection: WorkflowSelection) => void;
}) {
  return (
    <>
      {statuses.map((region) => (
        <div key={region.status.id}>
          <button
            type="button"
            aria-label={`Status ${region.status.id}`}
            data-testid={`status-region-${region.status.id}`}
            onClick={() =>
              onSelect({
                kind: "status",
                entity: region.status,
                complexity: region.complexity,
              })
            }
            className="absolute flex flex-col items-start justify-between rounded-(--radius-stamp) border border-(--color-edge) bg-(--color-paper) px-3 py-3 text-left shadow-[inset_0_0_0_1px_rgba(0,0,0,0.02)] transition-colors hover:bg-(--color-paper-3)"
            style={{
              left: `${region.x}px`,
              top: `${STATUS_Y}px`,
              width: `${region.width}px`,
              height: `${STATUS_HEIGHT}px`,
            }}
          >
            <span className="font-sans text-[18px] font-semibold text-(--color-ink) leading-tight">
              {region.status.label ?? region.status.id}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-(--color-ink-3)">
              pressure {region.complexity} · in {region.incoming} / out {region.outgoing}
            </span>
          </button>
          {region.drift.map((finding) => (
            <button
              key={`${region.status.id}:${finding.code}:${finding.message}`}
              type="button"
              onClick={() => onSelect({ kind: "drift", entity: finding })}
              aria-label="Drift"
              className="absolute inline-flex items-center gap-1 rounded-(--radius-stamp) border border-(--color-tripwire) bg-(--color-paper) px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.06em] text-(--color-tripwire)"
              style={{ left: `${region.x + 12}px`, top: `${STATUS_Y + STATUS_HEIGHT - 32}px` }}
            >
              <AlertTriangle size={12} /> drift
            </button>
          ))}
        </div>
      ))}
    </>
  );
}

function RouteLayer({ routes }: { routes: ProcessRoute[] }) {
  return (
    <svg
      aria-label="Workflow routes"
      className="pointer-events-none absolute inset-0"
      width="100%"
      height="100%"
    >
      <defs>
        {(["pm-agent", "coding-agent", "code"] as const).map((actor) => (
          <marker
            key={actor}
            id={`arrow-${actor}`}
            markerWidth="10"
            markerHeight="10"
            refX="8"
            refY="3"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M0,0 L0,6 L9,3 z" fill={actorColor(actor)} />
          </marker>
        ))}
      </defs>
      {routes.map((route) => {
        const actor = actorKey(route.actor);
        return (
          <path
            key={route.id}
            d={route.path}
            fill="none"
            stroke={actorColor(actor)}
            strokeWidth={route.kind === "return" || route.kind === "loop" ? 2.4 : 2}
            strokeDasharray={dashForKind(route.kind)}
            markerEnd={`url(#arrow-${actor})`}
          />
        );
      })}
    </svg>
  );
}

function RouteMarkers({
  routes,
  onSelect,
}: {
  routes: ProcessRoute[];
  onSelect: (selection: WorkflowSelection) => void;
}) {
  return (
    <>
      {routes.map((route) => (
        <div
          key={`${route.id}:markers`}
          className="absolute flex -translate-x-1/2 flex-col items-center gap-1"
          style={{ left: `${(route.fromX + route.toX) / 2}px`, top: `${route.y - 52}px` }}
        >
          {route.skills.length > 0 ? (
            <div className="flex max-w-[220px] flex-wrap justify-center gap-1">
              {route.skills.map((marker) => (
                <SkillButton key={marker.id} marker={marker} onSelect={onSelect} />
              ))}
            </div>
          ) : null}
          <RouteButton route={route} onSelect={onSelect} />
          <div className="flex flex-wrap justify-center gap-1">
            {route.command ? <CommandButton marker={route.command} onSelect={onSelect} /> : null}
            {route.gate ? <GateButton gate={route.gate} onSelect={onSelect} /> : null}
            {route.jitPrompts.map((marker) => (
              <JitPromptButton key={marker.id} marker={marker} onSelect={onSelect} />
            ))}
          </div>
        </div>
      ))}
    </>
  );
}

function RouteButton({
  route,
  onSelect,
}: {
  route: ProcessRoute;
  onSelect: (selection: WorkflowSelection) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect({ kind: "route", entity: route })}
      aria-label={`Route ${route.label}`}
      className="inline-flex items-center gap-1.5 rounded-(--radius-stamp) border border-(--color-edge) bg-(--color-paper) px-2 py-1 font-mono text-[10px] uppercase tracking-[0.06em] text-(--color-ink-2)"
    >
      <GitBranch size={13} style={{ color: actorColor(actorKey(route.actor)) }} />
      {route.label}
    </button>
  );
}

function CommandButton({
  marker,
  onSelect,
}: {
  marker: CommandMarker;
  onSelect: (selection: WorkflowSelection) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect({ kind: "command", entity: marker })}
      aria-label={`Command ${marker.command.label}`}
      className="inline-flex items-center gap-1 rounded-(--radius-stamp) border border-(--color-rule) bg-(--color-paper-2) px-2 py-1 font-mono text-[10px] uppercase tracking-[0.06em] text-(--color-rule)"
    >
      <SquareTerminal size={13} /> command
    </button>
  );
}

function SkillButton({
  marker,
  onSelect,
}: {
  marker: SkillMarker;
  onSelect: (selection: WorkflowSelection) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect({ kind: "skill", entity: marker })}
      aria-label={`Skill ${marker.skill.label}`}
      className="inline-flex items-center gap-1 rounded-(--radius-stamp) border border-(--color-edge) bg-(--color-paper-2) px-2 py-1 font-mono text-[10px] uppercase tracking-[0.06em] text-(--color-ink-2)"
    >
      <BookOpen size={13} /> skill
    </button>
  );
}

function GateButton({
  gate,
  onSelect,
}: {
  gate: GateCluster;
  onSelect: (selection: WorkflowSelection) => void;
}) {
  const total = gate.validators.length + gate.promptChecks.length;
  return (
    <button
      type="button"
      onClick={() => onSelect({ kind: "gate", entity: gate })}
      aria-label={`Gate on route ${gate.routeId}`}
      className="inline-flex items-center gap-1 rounded-(--radius-stamp) border border-(--color-gate) bg-(--color-paper-2) px-2 py-1 font-mono text-[10px] uppercase tracking-[0.06em] text-(--color-gate)"
    >
      <ShieldCheck size={13} /> {total} gate{total === 1 ? "" : "s"}
    </button>
  );
}

function JitPromptButton({
  marker,
  onSelect,
}: {
  marker: JitPromptMarker;
  onSelect: (selection: WorkflowSelection) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect({ kind: "jit_prompt", entity: marker.prompt })}
      aria-label={`JIT prompt ${marker.prompt.label}`}
      className="inline-flex items-center gap-1 rounded-(--radius-stamp) border border-(--color-tripwire) bg-(--color-paper-2) px-2 py-1 font-mono text-[10px] uppercase tracking-[0.06em] text-(--color-tripwire)"
    >
      <BellRing size={13} /> JIT
    </button>
  );
}

function EvidenceLayer({
  statuses,
  onSelect,
}: {
  statuses: TerritoryStatus[];
  onSelect: (selection: WorkflowSelection) => void;
}) {
  return (
    <>
      <div className="absolute left-6 right-6 top-[330px] flex flex-col items-center gap-1 font-mono text-[10px] uppercase tracking-[0.08em] text-(--color-ink-3)">
        <div className="h-px w-full bg-(--color-edge)" />
        <span>south: artifacts, logs, outputs, proof</span>
      </div>
      {statuses.map((region) => (
        <div
          key={`${region.status.id}:evidence`}
          className="absolute flex max-w-[240px] flex-wrap justify-center gap-1"
          style={{
            left: `${region.x + region.width / 2}px`,
            top: `${EVIDENCE_Y}px`,
            transform: "translateX(-50%)",
          }}
        >
          {region.artifacts.length === 0 ? (
            <span className="font-serif text-[12px] italic text-(--color-ink-3)">
              no declared proof
            </span>
          ) : (
            region.artifacts.map((marker) => (
              <ArtifactButton key={marker.id} marker={marker} onSelect={onSelect} />
            ))
          )}
        </div>
      ))}
    </>
  );
}

function ArtifactButton({
  marker,
  onSelect,
}: {
  marker: ArtifactMarker;
  onSelect: (selection: WorkflowSelection) => void;
}) {
  return (
    <button
      type="button"
      onClick={() =>
        onSelect({
          kind: "artifact",
          entity: marker.artifact,
          statusId: marker.statusId,
          direction: marker.direction,
        })
      }
      aria-label={`Artifact ${marker.artifact.label}`}
      className="inline-flex max-w-full items-center gap-1 rounded-(--radius-stamp) border border-(--color-edge) bg-(--color-paper) px-2 py-1 font-mono text-[11px] text-(--color-ink-2)"
    >
      <FileText size={13} />
      <span className="truncate">{marker.artifact.label}</span>
    </button>
  );
}

function Legend() {
  const chips: { label: string; tone: React.ComponentProps<typeof Stamp>["tone"] }[] = [
    { label: "STATUS TERRITORY", tone: "rule" },
    { label: "ACTOR ROUTE", tone: "info" },
    { label: "COMMAND", tone: "rule" },
    { label: "GATE", tone: "gate" },
    { label: "JIT PROMPT", tone: "tripwire" },
    { label: "SKILL", tone: "info" },
    { label: "ARTIFACT", tone: "info" },
  ];
  return (
    <section
      aria-label="Legend"
      className="flex flex-wrap items-center gap-2 rounded-(--radius-stamp) border border-(--color-edge) bg-(--color-paper) px-4 py-3"
    >
      {chips.map((chip) => (
        <Stamp key={chip.label} tone={chip.tone}>
          {chip.label}
        </Stamp>
      ))}
      <span className="ml-auto inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.08em] text-(--color-ink-3)">
        <Play size={12} color={actorColor("pm-agent")} /> PM
        <Play size={12} color={actorColor("coding-agent")} /> coding
        <Play size={12} color={actorColor("code")} /> code
      </span>
    </section>
  );
}

function actorKey(actor: string): "pm-agent" | "coding-agent" | "code" {
  if (actor === "pm-agent" || actor === "coding-agent") return actor;
  return "code";
}

function actorColor(actor: "pm-agent" | "coding-agent" | "code"): string {
  if (actor === "pm-agent") return "#8a5a16";
  if (actor === "coding-agent") return "#176b50";
  return "#315f7c";
}

function dashForKind(kind: ProcessRoute["kind"]): string | undefined {
  if (kind === "return") return "7 5";
  if (kind === "loop") return "3 4";
  if (kind === "side") return "10 5 2 5";
  return undefined;
}

function is404(err: unknown): boolean {
  return err instanceof ApiError && err.status === 404;
}

function StateFrame({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="flex flex-1 items-center justify-center rounded-(--radius-stamp) border border-(--color-edge) bg-(--color-paper-2) py-24"
      role="status"
    >
      {children}
    </div>
  );
}

function LoadingState() {
  return (
    <StateFrame>
      <p data-loading="workflow" className="font-serif text-[14px] italic text-(--color-ink-3)">
        Loading workflow...
      </p>
    </StateFrame>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <StateFrame>
      <div className="flex flex-col items-center gap-3">
        <p className="font-serif text-[14px] italic text-(--color-rule)">
          Couldn't load the workflow map.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-(--radius-stamp) border border-(--color-ink) bg-(--color-paper) px-3 py-1 font-mono text-[11px] uppercase tracking-[0.06em] text-(--color-ink) hover:bg-(--color-paper-3)"
        >
          Retry
        </button>
      </div>
    </StateFrame>
  );
}

function EmptyState() {
  return (
    <StateFrame>
      <p className="font-serif text-[14px] italic text-(--color-ink-3)">
        Workflow not yet available.
      </p>
    </StateFrame>
  );
}
