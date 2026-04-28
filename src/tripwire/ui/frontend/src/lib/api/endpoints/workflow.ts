import { useQuery } from "@tanstack/react-query";

import { pmRoleHeaders } from "@/lib/role";
import { ApiError, apiGet } from "../client";
import { queryKeys, staleTime } from "../queryKeys";

/**
 * Typed client for `/api/workflow` (Strand Y).
 *
 * The endpoint may not be live yet at S1-merge; consumers should treat
 * `data === undefined` as "no graph available, render empty
 * placeholders" and the typed shape is the contract once Strand Y
 * lands. See spec §2.1 for the response payload.
 */
export interface WorkflowStation {
  id: string;
  n: number;
  label: string;
  desc: string;
}

export interface WorkflowValidator {
  id: string;
  kind: "gate" | "tripwire";
  name: string;
  checks?: string;
  fires_on_station: string;
  fires_on_event?: string;
  blocks?: boolean;
  prompt_revealed?: string | null;
  prompt_redacted?: string | null;
  wired_to?: string[];
}

export interface WorkflowConnector {
  id: string;
  name: string;
  data?: string;
  wired_to_station?: string;
  wired_from_station?: string;
}

export interface WorkflowArtifact {
  id: string;
  label: string;
  produced_by: string;
  consumed_by: string | null;
}

export interface WorkflowGraph {
  project_id: string;
  lifecycle: { stations: WorkflowStation[] };
  validators: WorkflowValidator[];
  tripwires: WorkflowValidator[];
  connectors: { sources: WorkflowConnector[]; sinks: WorkflowConnector[] };
  artifacts: WorkflowArtifact[];
}

export const workflowApi = {
  /**
   * GET the orchestration graph for a project.
   *
   * `pmMode` toggles the `X-Tripwire-Role: pm` header so the
   * server fills `tripwires[*].prompt_revealed` with the
   * unredacted body (otherwise it returns `null`). The role gate
   * is a semantic separation, not auth — see `role_gate.py`.
   */
  get: (pid: string, opts?: { pmMode?: boolean }) =>
    apiGet<WorkflowGraph>(`/api/projects/${encodeURIComponent(pid)}/workflow`, {
      headers: pmRoleHeaders(Boolean(opts?.pmMode)),
    }),
};

export function useWorkflow(pid: string, opts?: { pmMode?: boolean }) {
  const pmMode = Boolean(opts?.pmMode);
  return useQuery<WorkflowGraph>({
    // PM-mode payload differs from default (tripwire prompt
    // bodies revealed); cache them under separate keys so toggling
    // role doesn't return a stale redacted graph.
    queryKey: [...queryKeys.workflow(pid), { pmMode }] as const,
    queryFn: () => workflowApi.get(pid, { pmMode }),
    staleTime: staleTime.default,
    // The endpoint is additive — until Strand Y ships, the backend
    // returns 404. Don't retry on a clean 404; surface as undefined to
    // the consumer so the Dashboard renders the empty wire shape.
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });
}
