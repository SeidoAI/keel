import { useState, type ReactNode } from "react";

import type {
  WorkflowArtifactRef,
  WorkflowDefinition,
  WorkflowRegistry,
  WorkflowRoute,
  WorkflowStatus,
} from "@/lib/api/endpoints/workflow";
import { skillCondition } from "./decorations";
import { GatePanel } from "./GatePanel";
import {
  TX_H,
  TX_W,
  type GateMode,
  type LaidOutEdge,
  type LaidOutJit,
  type LaidOutPort,
  type LaidOutRegion,
  type LaidOutTransition,
  type LaidOutTransitionRoute,
  layoutWorkflow,
  pathFromPoints,
} from "./layout";
import { ACTOR_COLOR, ACTOR_LABEL, isKnownActor } from "./tokens";

const DASH_BY_KIND: Record<string, string | undefined> = {
  return: "7 5",
  side: "10 4 2 4",
  loop: "4 4",
};

export type FlowSelection =
  | { kind: "status"; status: WorkflowStatus }
  | { kind: "route"; route: WorkflowRoute }
  | { kind: "jit_prompt"; id: string; statusId: string }
  | {
      kind: "artifact";
      artifact: WorkflowArtifactRef;
      statusId: string;
      direction: "produces" | "consumes";
    };

export interface WorkflowFlowchartProps {
  workflow: WorkflowDefinition;
  registry?: WorkflowRegistry;
  gateMode?: GateMode;
  onSelect?: (selection: FlowSelection) => void;
}

const actorColor = (actor: string): string =>
  isKnownActor(actor) ? ACTOR_COLOR[actor] : "var(--color-ink)";

const actorLabel = (actor: string): string =>
  isKnownActor(actor) ? ACTOR_LABEL[actor] : actor.toUpperCase();

export function WorkflowFlowchart({
  workflow,
  registry,
  gateMode = "diamond",
  onSelect,
}: WorkflowFlowchartProps) {
  const layout = layoutWorkflow(workflow, { gateMode });
  const [openedGate, setOpenedGate] = useState<string | null>(null);
  const openedTx = openedGate
    ? layout.transitions.find((t) => t.id === openedGate && t.kind === "transition")
    : null;
  const statusById = new Map(workflow.statuses.map((s) => [s.id, s]));

  const { width, height, regions, transitions, edges, jits, ports, mainY, proofTop } =
    layout;

  const handleGateToggle = (id: string) => {
    setOpenedGate((prev) => (prev === id ? null : id));
  };

  return (
    <div
      className="relative w-full"
      data-testid="workflow-flowchart"
      data-workflow={workflow.id}
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        style={{ display: "block" }}
        role="img"
        aria-label={`Workflow map for ${workflow.id}`}
      >
        <ArrowDefs />
        <rect width={width} height={height} fill="var(--color-paper)" />

        <CompassLabels width={width} height={height} />

        {regions.map((r, i) => (
          <RegionLayer
            key={r.id}
            region={r}
            index={i}
            proofTop={proofTop}
            status={statusById.get(r.id)}
            onSelect={onSelect}
          />
        ))}
        {regions.slice(1).map((r) => (
          <line
            key={`bd-${r.id}`}
            x1={r.x}
            y1={r.y}
            x2={r.x}
            y2={r.y + r.h}
            stroke="var(--color-edge)"
            strokeWidth={0.9}
            strokeOpacity={0.55}
          />
        ))}

        {regions[0] && regions[regions.length - 1] && (
          <line
            x1={regions[0].x + 8}
            y1={mainY}
            x2={
              regions[regions.length - 1]!.x +
              regions[regions.length - 1]!.w -
              8
            }
            y2={mainY}
            stroke="var(--color-edge)"
            strokeOpacity={0.4}
            strokeDasharray="2 6"
          />
        )}

        {edges.map((edge) => (
          <EdgeLine key={edge.id} edge={edge} />
        ))}

        {edges
          .filter((e) => e.outcomeLabel)
          .map((edge) => (
            <OutcomeLabel key={`ol-${edge.id}`} edge={edge} />
          ))}

        {jits.map((jit) => (
          <JitNode
            key={jit.id}
            jit={jit}
            onClick={() =>
              onSelect?.({ kind: "jit_prompt", id: jit.label, statusId: jit.status })
            }
          />
        ))}

        {transitions.map((tx) => (
          <TransitionNode
            key={tx.id}
            tx={tx}
            opened={openedGate === tx.id}
            onGateToggle={handleGateToggle}
            onSelect={onSelect}
          />
        ))}

        {regions.map((r) => {
          const produces = r.artifacts?.produces ?? [];
          const a = produces[0];
          if (!a) return null;
          return (
            <ArtifactTile
              key={`art-${r.id}-${a.id}`}
              label={a.label}
              x={r.cx}
              y={layout.artifactRowY}
              onClick={() =>
                onSelect?.({
                  kind: "artifact",
                  artifact: a,
                  statusId: r.id,
                  direction: "produces",
                })
              }
            />
          );
        })}

        {ports.map((p) => (
          <PortNode key={p.id} port={p} />
        ))}
      </svg>

      {openedTx && openedTx.kind === "transition" && (
        <GatePanel
          tx={openedTx}
          chartWidth={width}
          chartHeight={height}
          registry={registry}
          onClose={() => setOpenedGate(null)}
        />
      )}
    </div>
  );
}

function ArrowDefs() {
  return (
    <defs>
      {(["pm-agent", "coding-agent", "code"] as const).map((actor) => (
        <marker
          key={actor}
          id={`fc-arrow-${actor}`}
          viewBox="0 0 10 10"
          refX={9}
          refY={5}
          markerWidth={7}
          markerHeight={7}
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 Z" fill={ACTOR_COLOR[actor]} />
        </marker>
      ))}
    </defs>
  );
}

function CompassLabels({ width, height }: { width: number; height: number }) {
  return (
    <g
      fontFamily="var(--font-mono)"
      fontSize={9.5}
      fill="var(--color-ink-3)"
      letterSpacing="0.18em"
    >
      <text x={40} y={28}>
        WEST · INTENT
      </text>
      <text x={width / 2} y={28} textAnchor="middle">
        NORTH · CONTROL
      </text>
      <text x={width - 40} y={28} textAnchor="end">
        EAST · CLOSURE
      </text>
      <text x={width / 2} y={height - 12} textAnchor="middle">
        SOUTH · PROOF
      </text>
    </g>
  );
}

interface RegionLayerProps {
  region: LaidOutRegion;
  index: number;
  proofTop: number;
  status?: WorkflowStatus;
  onSelect?: (s: FlowSelection) => void;
}

function RegionLayer({ region, index, proofTop, status, onSelect }: RegionLayerProps) {
  const fill = index % 2 === 0 ? "#efebde" : "#e8e2cf";
  const handleClick = status
    ? () => onSelect?.({ kind: "status", status })
    : undefined;
  return (
    <g
      data-testid={`workflow-region-${region.id}`}
      onClick={handleClick}
      style={handleClick ? { cursor: "pointer" } : undefined}
    >
      <rect
        x={region.x}
        y={region.y}
        width={region.w}
        height={region.h}
        fill={fill}
        stroke="var(--color-edge)"
        strokeWidth={0.7}
        strokeOpacity={0.7}
      />
      <text
        x={region.x + 12}
        y={region.y + 22}
        fontFamily="var(--font-mono)"
        fontSize={9.5}
        fill="var(--color-ink-3)"
        letterSpacing="0.18em"
      >
        {String(index + 1).padStart(2, "0")} · STATUS
      </text>
      <text
        x={region.x + 12}
        y={region.y + 48}
        fontFamily="var(--font-sans)"
        fontWeight={600}
        fontSize={22}
        fill="var(--color-ink)"
        letterSpacing="-0.015em"
      >
        {region.id}
      </text>
      {region.blurb && (
        <text
          x={region.x + 12}
          y={region.y + 68}
          fontFamily="var(--font-serif)"
          fontStyle="italic"
          fontSize={13}
          fill="var(--color-ink-2)"
        >
          {region.blurb}
        </text>
      )}
      {region.terminal && (
        <circle
          cx={region.x + region.w - 14}
          cy={region.y + 14}
          r={6}
          fill="var(--color-ink)"
        />
      )}
      <line
        x1={region.x + 8}
        y1={region.y + 80}
        x2={region.x + region.w - 8}
        y2={region.y + 80}
        stroke="var(--color-edge)"
        strokeOpacity={0.5}
      />
      <line
        x1={region.x + 8}
        y1={proofTop - 8}
        x2={region.x + region.w - 8}
        y2={proofTop - 8}
        stroke="var(--color-edge)"
        strokeOpacity={0.45}
        strokeDasharray="3 4"
      />
      <text
        x={region.x + 12}
        y={proofTop + 6}
        fontFamily="var(--font-mono)"
        fontSize={8.5}
        fill="var(--color-ink-3)"
        letterSpacing="0.18em"
      >
        PROOF SHELF
      </text>
    </g>
  );
}

function EdgeLine({ edge }: { edge: LaidOutEdge }) {
  const c = actorColor(edge.actor);
  const dash = DASH_BY_KIND[edge.kind] ?? undefined;
  const markerEnd = edge.isOut && isKnownActor(edge.actor)
    ? `url(#fc-arrow-${edge.actor})`
    : undefined;
  return (
    <path
      d={pathFromPoints(edge.points, 9)}
      stroke={c}
      strokeWidth={2}
      fill="none"
      strokeDasharray={dash}
      markerEnd={markerEnd}
    />
  );
}

function OutcomeLabel({ edge }: { edge: LaidOutEdge }) {
  if (!edge.outcomeLabel) return null;
  const p = edge.points[Math.floor(edge.points.length / 2)];
  if (!p) return null;
  const c = actorColor(edge.actor);
  return (
    <g transform={`translate(${p.x} ${p.y - 14})`}>
      <rect
        x={-32}
        y={-9}
        width={64}
        height={14}
        fill="var(--color-paper)"
        stroke={c}
        strokeWidth={0.9}
      />
      <text
        x={0}
        y={2}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
        fontSize={9}
        fill="var(--color-ink)"
        letterSpacing="0.04em"
      >
        {edge.outcomeLabel}
      </text>
    </g>
  );
}

interface TransitionNodeProps {
  tx: LaidOutTransition;
  opened: boolean;
  onGateToggle: (id: string) => void;
  onSelect?: (s: FlowSelection) => void;
}

function TransitionNode({ tx, opened, onGateToggle, onSelect }: TransitionNodeProps) {
  if (tx.kind === "branch") {
    return <BranchDiamond tx={tx} />;
  }
  return (
    <RouteTransitionNode
      tx={tx}
      opened={opened}
      onGateToggle={onGateToggle}
      onSelect={onSelect}
    />
  );
}

interface RouteTransitionNodeProps {
  tx: LaidOutTransitionRoute;
  opened: boolean;
  onGateToggle: (id: string) => void;
  onSelect?: (s: FlowSelection) => void;
}

function RouteTransitionNode({
  tx,
  opened,
  onGateToggle,
  onSelect,
}: RouteTransitionNodeProps) {
  const r = tx.route;
  const c = actorColor(r.actor);
  const skills = r.skills ?? [];
  const validators = r.controls?.validators ?? [];
  const promptChecks = r.controls?.prompt_checks ?? [];
  const gateCount = validators.length + promptChecks.length;
  const handleClick = () => onSelect?.({ kind: "route", route: r });

  return (
    <g
      transform={`translate(${tx.cx} ${tx.cy})`}
      data-testid={`workflow-transition-${r.id}`}
      onClick={handleClick}
      style={onSelect ? { cursor: "pointer" } : undefined}
    >
      {skills.length > 0 && <SkillRibbon routeId={r.id} skills={skills} />}

      <rect
        x={-TX_W / 2}
        y={-TX_H / 2}
        width={TX_W}
        height={TX_H}
        fill="var(--color-paper)"
        stroke={c}
        strokeWidth={1.6}
        rx={3}
      />
      <rect x={-TX_W / 2} y={-TX_H / 2} width={4} height={TX_H} fill={c} />

      {r.command && (
        <text
          x={-TX_W / 2 + 12}
          y={-TX_H / 2 + 14}
          fontFamily="var(--font-mono)"
          fontSize={9.5}
          fill="var(--color-ink-3)"
          letterSpacing="0.04em"
        >
          ▷ {r.command}
        </text>
      )}
      <text
        x={-TX_W / 2 + 12}
        y={r.command ? -TX_H / 2 + 30 : -2}
        fontFamily="var(--font-sans)"
        fontWeight={600}
        fontSize={13}
        fill="var(--color-ink)"
        letterSpacing="-0.005em"
      >
        {r.label}
      </text>
      <text
        x={TX_W / 2 - 8}
        y={TX_H / 2 - 8}
        textAnchor="end"
        fontFamily="var(--font-mono)"
        fontSize={8.5}
        fontWeight={600}
        fill={c}
        letterSpacing="0.06em"
      >
        {actorLabel(r.actor)}
      </text>

      {gateCount > 0 && (
        <GateBadge
          routeId={r.id}
          count={gateCount}
          opened={opened}
          onToggle={() => onGateToggle(tx.id)}
        />
      )}
    </g>
  );
}

function SkillRibbon({ routeId, skills }: { routeId: string; skills: string[] }) {
  const visible = skills.slice(0, 3);
  return (
    <g>
      {visible.map((s, i) => {
        const cond = skillCondition(routeId, s);
        const short = s.length > 14 ? `${s.slice(0, 12)}…` : s;
        return (
          <text
            key={s}
            x={-TX_W / 2 + 4}
            y={-TX_H / 2 - 14 - (visible.length - 1 - i) * 11}
            fontFamily="var(--font-mono)"
            fontSize={8.5}
            fill="var(--color-info)"
            letterSpacing="0.02em"
          >
            ▸{" "}
            <tspan
              style={
                cond
                  ? {
                      textDecoration: "underline",
                      textDecorationStyle: "dotted",
                    }
                  : undefined
              }
            >
              {short}
            </tspan>
            {cond ? "?" : ""}
          </text>
        );
      })}
    </g>
  );
}

interface GateBadgeProps {
  routeId: string;
  count: number;
  opened: boolean;
  onToggle: () => void;
}

function GateBadge({ routeId, count, opened, onToggle }: GateBadgeProps) {
  return (
    <g
      transform={`translate(${TX_W / 2 - 44} ${-TX_H / 2 + 4})`}
      data-testid={`workflow-gate-badge-${routeId}`}
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      style={{ cursor: "pointer" }}
      role="button"
      aria-pressed={opened}
      aria-label={`Gate on route ${routeId}: ${count} checks`}
    >
      <rect
        x={0}
        y={0}
        width={40}
        height={14}
        fill="var(--color-paper-2)"
        stroke="var(--color-gate)"
        strokeWidth={1}
      />
      <path
        d="M 4 9 V 7 a2 2 0 0 1 4 0 V 9"
        stroke="var(--color-gate)"
        strokeWidth={1}
        fill="none"
      />
      <rect
        x={3}
        y={9}
        width={6}
        height={4}
        stroke="var(--color-gate)"
        strokeWidth={1}
        fill="none"
      />
      <text
        x={14}
        y={10}
        fontFamily="var(--font-mono)"
        fontSize={9}
        fontWeight={600}
        fill="var(--color-gate)"
        letterSpacing="0.04em"
      >
        ×{count}
      </text>
    </g>
  );
}

function BranchDiamond({ tx }: { tx: Extract<LaidOutTransition, { kind: "branch" }> }) {
  const c = actorColor(tx.actor);
  const half = 32;
  const wide = 60;
  return (
    <g
      transform={`translate(${tx.cx} ${tx.cy})`}
      data-testid={`workflow-branch-${tx.command}`}
    >
      <polygon
        points={`0,${-half} ${wide},0 0,${half} ${-wide},0`}
        fill="var(--color-paper)"
        stroke={c}
        strokeWidth={1.6}
      />
      <text
        x={0}
        y={-2}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
        fontSize={9.5}
        fill="var(--color-ink-3)"
      >
        ▷ {tx.command}
      </text>
      <text
        x={0}
        y={14}
        textAnchor="middle"
        fontFamily="var(--font-sans)"
        fontWeight={600}
        fontSize={12}
        fill="var(--color-ink)"
      >
        decision
      </text>
    </g>
  );
}

function JitNode({ jit, onClick }: { jit: LaidOutJit; onClick?: () => void }) {
  return (
    <g
      transform={`translate(${jit.x} ${jit.y})`}
      data-testid={`workflow-jit-${jit.id}`}
      onClick={onClick}
      style={onClick ? { cursor: "pointer" } : undefined}
      role={onClick ? "button" : undefined}
      aria-label={onClick ? `JIT prompt ${jit.label}` : undefined}
    >
      <rect
        x={-13}
        y={-13}
        width={26}
        height={26}
        rx={6}
        ry={6}
        fill="var(--color-paper)"
        stroke="var(--color-tripwire)"
        strokeWidth={1.5}
      />
      <text
        x={0}
        y={4}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
        fontSize={13}
        fontWeight={700}
        fill="var(--color-tripwire)"
      >
        !
      </text>
      <text
        x={0}
        y={28}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
        fontSize={8.5}
        fill="var(--color-ink-2)"
        letterSpacing="0.02em"
      >
        {jit.label}
      </text>
    </g>
  );
}

function ArtifactTile({
  label,
  x,
  y,
  onClick,
}: {
  label: string;
  x: number;
  y: number;
  onClick?: () => void;
}): ReactNode {
  return (
    <g
      transform={`translate(${x} ${y})`}
      onClick={onClick}
      style={onClick ? { cursor: "pointer" } : undefined}
      role={onClick ? "button" : undefined}
      aria-label={onClick ? `Artifact ${label}` : undefined}
    >
      <g transform="translate(-58, 0)">
        <path
          d="M 0 0 H 100 L 116 12 V 30 H 0 Z"
          fill="var(--color-paper)"
          stroke="var(--color-ink-3)"
          strokeDasharray="3 2"
          strokeWidth={0.9}
        />
        <path
          d="M 100 0 V 12 H 116"
          fill="none"
          stroke="var(--color-ink-3)"
          strokeWidth={0.9}
          strokeDasharray="3 2"
        />
        <text
          x={58}
          y={20}
          textAnchor="middle"
          fontFamily="var(--font-mono)"
          fontSize={9.5}
          fill="var(--color-ink-2)"
        >
          ◫ {label}
        </text>
      </g>
    </g>
  );
}

function PortNode({ port }: { port: LaidOutPort }) {
  return (
    <g transform={`translate(${port.x} ${port.y})`}>
      <circle
        r={9}
        fill={port.kind === "sink" ? "var(--color-ink)" : "var(--color-paper)"}
        stroke="var(--color-ink)"
        strokeWidth={1.6}
      />
      {port.kind === "source" && <circle r={2.5} fill="var(--color-ink)" />}
      <text
        x={port.kind === "source" ? -14 : 14}
        y={3}
        textAnchor={port.kind === "source" ? "end" : "start"}
        fontFamily="var(--font-mono)"
        fontSize={10}
        fill="var(--color-ink-2)"
        letterSpacing="0.04em"
      >
        {port.label}
      </text>
      <text
        x={port.kind === "source" ? -14 : 14}
        y={16}
        textAnchor={port.kind === "source" ? "end" : "start"}
        fontFamily="var(--font-mono)"
        fontSize={8}
        fill="var(--color-ink-3)"
        letterSpacing="0.12em"
      >
        {port.kind.toUpperCase()}
      </text>
    </g>
  );
}
