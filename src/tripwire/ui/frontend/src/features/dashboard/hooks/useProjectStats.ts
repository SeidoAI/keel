import { useQuery } from "@tanstack/react-query";

import {
  SESSION_STAGES,
  type StageBucket,
  sessionStageId,
  UNASSIGNED_STAGE_ID,
} from "@/components/ui/session-stage-row";
import { type EnumDescriptor, enumsApi } from "@/lib/api/endpoints/enums";
import { type IssueSummary, issuesApi } from "@/lib/api/endpoints/issues";
import { type SessionSummary, sessionsApi } from "@/lib/api/endpoints/sessions";
import { queryKeys, staleTime } from "@/lib/api/queryKeys";

export interface StatusCount {
  value: string;
  label: string;
  color: string | null;
  count: number;
}

/**
 * Aggregate status → count rows for the dashboard, ordered by the
 * project's `issue_status` enum. Values absent from the enum are
 * dropped rather than appended — the enum is the source of truth for
 * what columns the UI shows, and an unexpected value almost always
 * means a typo in an issue file that validation will surface.
 */
export function computeStatusCounts(
  issues: IssueSummary[],
  statusEnum: EnumDescriptor | undefined,
): StatusCount[] {
  if (!statusEnum) return [];
  const counts = new Map<string, number>();
  for (const issue of issues) {
    counts.set(issue.status, (counts.get(issue.status) ?? 0) + 1);
  }
  return statusEnum.values.map((v) => ({
    value: v.value,
    label: v.label,
    color: v.color,
    count: counts.get(v.value) ?? 0,
  }));
}

export function useIssuesList(pid: string) {
  return useQuery({
    queryKey: queryKeys.issues(pid),
    queryFn: () => issuesApi.list(pid),
    staleTime: staleTime.default,
  });
}

export function useIssueStatusEnum(pid: string) {
  return useQuery({
    queryKey: queryKeys.enum(pid, "issue_status"),
    queryFn: () => enumsApi.get(pid, "issue_status"),
    staleTime: staleTime.enum,
  });
}

export function useSessionsList(pid: string) {
  return useQuery({
    queryKey: queryKeys.sessions(pid),
    queryFn: () => sessionsApi.list(pid),
    staleTime: staleTime.default,
  });
}

/**
 * Bucket sessions + issues by canonical lifecycle stage for the
 * top-of-dashboard SessionStageRow.
 *
 * The session stage is the source of truth for issue placement: every
 * issue assigned to a session counts under that session's stage,
 * regardless of the issue's own status. Drift cases (session
 * `in_review` with issues `done`) count under the session stage —
 * the drift itself is a separate signal handled by the inbox.
 *
 * Issues with no session land in the `unassigned` bucket. Off-track
 * sessions (failed/paused/abandoned) and their issues are not
 * counted in any bucket — they surface via the attention queue.
 */
export function bucketByStage(
  sessions: SessionSummary[],
  issues: IssueSummary[],
): Record<string, StageBucket> {
  const buckets: Record<string, StageBucket> = {
    [UNASSIGNED_STAGE_ID]: { sessionCount: 0, issueCount: 0 },
  };
  for (const stage of SESSION_STAGES) {
    buckets[stage.id] = { sessionCount: 0, issueCount: 0 };
  }
  const bump = (stageId: string, key: keyof StageBucket) => {
    const bucket = buckets[stageId];
    if (bucket) bucket[key] += 1;
  };
  const issueToSessionStage = new Map<string, string>();
  for (const session of sessions) {
    const stageId = sessionStageId(session.status);
    if (!stageId) continue; // off-track — skipped
    bump(stageId, "sessionCount");
    for (const issueId of session.issues) {
      issueToSessionStage.set(issueId, stageId);
    }
  }
  for (const issue of issues) {
    const stageId = issueToSessionStage.get(issue.id);
    bump(stageId ?? UNASSIGNED_STAGE_ID, "issueCount");
  }
  return buckets;
}

export interface ProjectStats {
  statusCounts: StatusCount[];
  totalIssues: number;
  sessions: SessionSummary[];
  issues: IssueSummary[];
  buckets: Record<string, StageBucket>;
  isLoading: boolean;
  isError: boolean;
}

export function useProjectStats(pid: string): ProjectStats {
  const issues = useIssuesList(pid);
  const statusEnum = useIssueStatusEnum(pid);
  const sessions = useSessionsList(pid);

  const statusCounts = computeStatusCounts(issues.data ?? [], statusEnum.data);
  const buckets = bucketByStage(sessions.data ?? [], issues.data ?? []);

  return {
    statusCounts,
    totalIssues: issues.data?.length ?? 0,
    sessions: sessions.data ?? [],
    issues: issues.data ?? [],
    buckets,
    isLoading: issues.isLoading || statusEnum.isLoading || sessions.isLoading,
    isError: issues.isError || statusEnum.isError || sessions.isError,
  };
}
