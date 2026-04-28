import { useMemo } from "react";

import type {
  WorkflowArtifact,
  WorkflowConnector,
  WorkflowGraph,
  WorkflowStation,
  WorkflowValidator,
} from "@/lib/api/endpoints/workflow";

/**
 * Fixed canvas constants for the workflow map.
 *
 * The 1380×820 SVG body sits inside a 1440×1180 page artboard per
 * spec §3.6. Stations evenly spaced on a horizontal wire at
 * `wireY`; sources stacked in the LEFT gutter; sinks in the RIGHT
 * gutter; validators + tripwires above the wire above their
 * `fires_on_station`; artifacts below the wire under
 * `produced_by`.
 *
 * Layout is deterministic by entity-kind and by position in the
 * input array — keeps the rendered output stable when the API
 * registers a new entity (the diff is "one row added," not "the
 * whole graph relays out").
 */
export const WORKFLOW_CANVAS = {
  width: 1380,
  height: 820,
  wireY: 420,
  gutterLeft: 200,
  gutterRight: 200,
  validatorRowHeight: 86,
  validatorRowGap: 60,
  tripwireRowGap: 36,
  artifactRowGap: 60,
  artifactRowHeight: 86,
  connectorRowGap: 70,
  connectorRowOffset: 40,
} as const;

export interface PositionedStation extends WorkflowStation {
  x: number;
  y: number;
}

export interface PositionedValidator extends WorkflowValidator {
  x: number;
  y: number;
  /** 0-based stack index above the wire at this station. */
  stackIndex: number;
}

export interface PositionedArtifact extends WorkflowArtifact {
  x: number;
  y: number;
}

export interface PositionedConnector extends WorkflowConnector {
  x: number;
  y: number;
  /** Station-id this connector lands on (sources) or leaves from (sinks). */
  attachStation: string | undefined;
}

export interface WorkflowLayout {
  stations: PositionedStation[];
  validators: PositionedValidator[];
  tripwires: PositionedValidator[];
  artifacts: PositionedArtifact[];
  sources: PositionedConnector[];
  sinks: PositionedConnector[];
}

/**
 * Pure layout computation. The hook wrapper memoises against the
 * graph identity; callers usually pass the TanStack Query cached
 * object directly so re-renders that don't change the data don't
 * re-lay-out.
 */
export function computeWorkflowLayout(graph: WorkflowGraph): WorkflowLayout {
  const stations = layoutStations(graph.lifecycle.stations);
  const stationXById = new Map(stations.map((s) => [s.id, s.x] as const));

  const validatorStackByStation = new Map<string, number>();
  const validators: PositionedValidator[] = graph.validators.map((v) => {
    const idx = validatorStackByStation.get(v.fires_on_station) ?? 0;
    validatorStackByStation.set(v.fires_on_station, idx + 1);
    const x = stationXById.get(v.fires_on_station) ?? WORKFLOW_CANVAS.width / 2;
    const y =
      WORKFLOW_CANVAS.wireY -
      WORKFLOW_CANVAS.validatorRowGap -
      idx * WORKFLOW_CANVAS.validatorRowHeight;
    return { ...v, x, y, stackIndex: idx };
  });

  // Tripwires stack above the validator stack at each station, so a
  // station with 2 validators + 1 tripwire renders [t1, v2, v1] from
  // top down. The visual band is "above the wire," and tripwires
  // sit higher to reinforce the cognitive ordering: gates first
  // (closer to the wire they gate), tripwires further out (loud,
  // attention-getting).
  const tripwires: PositionedValidator[] = graph.tripwires.map((t) => {
    const validatorCount = validatorStackByStation.get(t.fires_on_station) ?? 0;
    const tripwireOffset = validatorStackByStation.get(`__tw__${t.fires_on_station}`) ?? 0;
    validatorStackByStation.set(`__tw__${t.fires_on_station}`, tripwireOffset + 1);
    const x = stationXById.get(t.fires_on_station) ?? WORKFLOW_CANVAS.width / 2;
    const y =
      WORKFLOW_CANVAS.wireY -
      WORKFLOW_CANVAS.validatorRowGap -
      validatorCount * WORKFLOW_CANVAS.validatorRowHeight -
      WORKFLOW_CANVAS.tripwireRowGap -
      tripwireOffset * WORKFLOW_CANVAS.validatorRowHeight;
    return { ...t, x, y, stackIndex: validatorCount + tripwireOffset };
  });

  const artifactStackByStation = new Map<string, number>();
  const artifacts: PositionedArtifact[] = graph.artifacts.map((a) => {
    const idx = artifactStackByStation.get(a.produced_by) ?? 0;
    artifactStackByStation.set(a.produced_by, idx + 1);
    const x = stationXById.get(a.produced_by) ?? WORKFLOW_CANVAS.width / 2;
    const y =
      WORKFLOW_CANVAS.wireY +
      WORKFLOW_CANVAS.artifactRowGap +
      idx * WORKFLOW_CANVAS.artifactRowHeight;
    return { ...a, x, y };
  });

  const sources: PositionedConnector[] = graph.connectors.sources.map((c, i) => ({
    ...c,
    attachStation: c.wired_to_station,
    x: WORKFLOW_CANVAS.gutterLeft - WORKFLOW_CANVAS.connectorRowOffset,
    y:
      WORKFLOW_CANVAS.wireY -
      ((graph.connectors.sources.length - 1) / 2) * WORKFLOW_CANVAS.connectorRowGap +
      i * WORKFLOW_CANVAS.connectorRowGap,
  }));

  const sinks: PositionedConnector[] = graph.connectors.sinks.map((c, i) => ({
    ...c,
    attachStation: c.wired_from_station,
    x: WORKFLOW_CANVAS.width - WORKFLOW_CANVAS.gutterRight + WORKFLOW_CANVAS.connectorRowOffset,
    y:
      WORKFLOW_CANVAS.wireY -
      ((graph.connectors.sinks.length - 1) / 2) * WORKFLOW_CANVAS.connectorRowGap +
      i * WORKFLOW_CANVAS.connectorRowGap,
  }));

  return { stations, validators, tripwires, artifacts, sources, sinks };
}

function layoutStations(stations: WorkflowStation[]): PositionedStation[] {
  if (stations.length === 0) return [];
  const innerW = WORKFLOW_CANVAS.width - WORKFLOW_CANVAS.gutterLeft - WORKFLOW_CANVAS.gutterRight;
  const stepX = innerW / Math.max(stations.length - 1, 1);
  return stations.map((s, i) => ({
    ...s,
    x: WORKFLOW_CANVAS.gutterLeft + i * stepX,
    y: WORKFLOW_CANVAS.wireY,
  }));
}

export function useWorkflowLayout(graph: WorkflowGraph | undefined): WorkflowLayout | undefined {
  return useMemo(() => (graph ? computeWorkflowLayout(graph) : undefined), [graph]);
}
