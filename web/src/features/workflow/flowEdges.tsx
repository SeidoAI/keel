import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";

import { CROSSLINK_BUS_X, Y_DEEP_RETURN } from "./flowGraph";
import { ACTOR_COLOR, isKnownActor } from "./tokens";

export interface ActorEdgeData extends Record<string, unknown> {
  actor: string;
  kind: string;
  label?: string;
}

const DASH_BY_KIND: Record<string, string | undefined> = {
  return: "7 5",
  side: "10 4 2 4",
  loop: "4 4",
};

const actorStroke = (actor: string): string =>
  isKnownActor(actor) ? ACTOR_COLOR[actor] : "var(--color-ink)";

export function ActorEdge(props: EdgeProps) {
  const {
    id,
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    markerEnd,
    data,
  } = props;
  const d = (data ?? {}) as ActorEdgeData;
  const stroke = actorStroke(d.actor);
  const dash = DASH_BY_KIND[d.kind];

  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 12,
  });

  return (
    <>
      <BaseEdge
        path={path}
        markerEnd={markerEnd}
        style={{
          stroke,
          strokeWidth: 2,
          strokeDasharray: dash,
        }}
      />
      {d.label && (
        <EdgeLabelRenderer>
          <div
            data-testid={`workflow-edge-label-${id}`}
            className="nodrag nopan"
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              padding: "2px 8px",
              background: "var(--color-paper)",
              border: `1px solid ${stroke}`,
              borderRadius: 2,
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              color: "var(--color-ink)",
              letterSpacing: "0.04em",
              pointerEvents: "all",
              whiteSpace: "nowrap",
              zIndex: 50,
              boxShadow: "0 0 0 3px var(--color-paper)",
            }}
          >
            {d.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

// ── CrossLinkEdge: connects a status in one workflow band to a status
// in another. Routes south out of the source region's bottom, traverses
// the inter-band gutter, then drops into the target band on a dedicated
// lane *above* the inputs band — so the cross-link never crosses any
// material-input chip docking on the same north edge. Distinct visual
// (dashed indigo) marks it as a cross-workflow link, not an intra-workflow
// transition.
export interface CrossLinkEdgeData extends Record<string, unknown> {
  sourceWorkflow: string;
  label?: string | null;
}

// Cross-link colour — picked to stand apart from every actor hue:
//   pm-agent (var(--color-tripwire) #b8741a ochre)
//   coding-agent (var(--color-gate) #2d5a3d green)
//   code (var(--color-info) #2d3a7c indigo)
// Teal sits diagonally opposite all three on the wheel and reads as
// "this is metadata, not a route."
const CROSSLINK_HEX = "#0e7c8a";

export function CrossLinkEdge(props: EdgeProps) {
  const { id, sourceX, sourceY, targetX, targetY, markerEnd, data } = props;
  const d = (data ?? {}) as CrossLinkEdgeData;
  const stroke = CROSSLINK_HEX;
  const dash = "4 4";
  const r = 12;

  // Route every cross-link through a shared vertical bus on the far
  // left of the canvas (CROSSLINK_BUS_X). Path:
  //   source dot ↓
  //     ↓ short drop into the gutter just below source band
  //     ← west across the gutter to the bus
  //     ↓/↑ along the bus to the gutter just above target band
  //     → east across that gutter to under target dot
  //     ↓ into target dot
  // Horizontal segments live in inter-band gutters; vertical segment
  // lives in the bus. Nothing crosses an unrelated status region.
  const busX = CROSSLINK_BUS_X;
  // Drop just below the source dot (it sits at the south edge of a
  // status region, with the gutter immediately below it).
  const sourceTurnY = sourceY + 32;
  // Rise to just above the target dot (target dot is at north edge).
  const targetTurnY = targetY - 32;

  const path = [
    `M ${sourceX} ${sourceY}`,
    `L ${sourceX} ${sourceTurnY - r}`,
    `Q ${sourceX} ${sourceTurnY}, ${sourceX - r} ${sourceTurnY}`,
    `L ${busX + r} ${sourceTurnY}`,
    `Q ${busX} ${sourceTurnY}, ${busX} ${sourceTurnY + (targetTurnY > sourceTurnY ? r : -r)}`,
    `L ${busX} ${targetTurnY - (targetTurnY > sourceTurnY ? r : -r)}`,
    `Q ${busX} ${targetTurnY}, ${busX + r} ${targetTurnY}`,
    `L ${targetX - r} ${targetTurnY}`,
    `Q ${targetX} ${targetTurnY}, ${targetX} ${targetTurnY + r}`,
    `L ${targetX} ${targetY}`,
  ].join(" ");

  // Label sits at the bus, vertically centred between the two turns.
  const labelX = busX;
  const labelY = (sourceTurnY + targetTurnY) / 2;

  return (
    <>
      <BaseEdge
        path={path}
        markerEnd={markerEnd}
        style={{
          stroke,
          strokeWidth: 1.5,
          strokeDasharray: dash,
          fill: "none",
        }}
      />
      <EdgeLabelRenderer>
        <div
          data-testid={`workflow-crosslink-label-${id}`}
          className="nodrag nopan"
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            padding: "2px 10px",
            background: "var(--color-paper)",
            border: `1px dashed ${stroke}`,
            borderRadius: 2,
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: stroke,
            letterSpacing: "0.06em",
            pointerEvents: "all",
            whiteSpace: "nowrap",
            zIndex: 50,
            boxShadow: "0 0 0 4px var(--color-paper)",
          }}
        >
          ↗ {d.label ?? d.sourceWorkflow}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

// ── ReturnEdge: a south-routed step path used for backwards (return)
// outcomes from a branch diamond. Path goes:
//   source → straight down to Y_DEEP_RETURN → west across to target X
//   → straight up into target. Label sits on the deep horizontal segment,
// well below any forward arrows.
export function ReturnEdge(props: EdgeProps) {
  const { id, sourceX, sourceY, targetX, targetY, markerEnd, data } = props;
  const d = (data ?? {}) as ActorEdgeData;
  const stroke = actorStroke(d.actor);
  const dash = "7 5";
  const deep = Y_DEEP_RETURN;

  // step path with rounded corners
  const r = 18;
  const path = [
    `M ${sourceX} ${sourceY}`,
    `L ${sourceX} ${deep - r}`,
    `Q ${sourceX} ${deep}, ${sourceX - r} ${deep}`,
    `L ${targetX + r} ${deep}`,
    `Q ${targetX} ${deep}, ${targetX} ${deep - r}`,
    `L ${targetX} ${targetY}`,
  ].join(" ");

  const labelX = (sourceX + targetX) / 2;
  const labelY = deep;

  return (
    <>
      <BaseEdge
        path={path}
        markerEnd={markerEnd}
        style={{
          stroke,
          strokeWidth: 2,
          strokeDasharray: dash,
          fill: "none",
        }}
      />
      {d.label && (
        <EdgeLabelRenderer>
          <div
            data-testid={`workflow-edge-label-${id}`}
            className="nodrag nopan"
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              padding: "3px 10px",
              background: "var(--color-paper)",
              border: `1.2px solid ${stroke}`,
              borderRadius: 2,
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              color: "var(--color-ink)",
              letterSpacing: "0.04em",
              pointerEvents: "all",
              whiteSpace: "nowrap",
              zIndex: 60,
              boxShadow: "0 0 0 4px var(--color-paper)",
            }}
          >
            {d.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
