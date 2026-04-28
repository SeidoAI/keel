import { describe, expect, it, vi } from "vitest";

import { workflowApi } from "@/lib/api/endpoints/workflow";
import { queryKeys } from "@/lib/api/queryKeys";

function mockFetch() {
  const res = {
    ok: true,
    status: 200,
    json: () =>
      Promise.resolve({
        project_id: "p1",
        lifecycle: { stations: [] },
        validators: [],
        tripwires: [],
        connectors: { sources: [], sinks: [] },
        artifacts: [],
      }),
  } as Response;
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(res);
}

describe("workflowApi.get — PM-mode header threading", () => {
  it("sends X-Tripwire-Role: pm when pmMode is true", async () => {
    const spy = mockFetch();
    await workflowApi.get("p1", { pmMode: true });
    expect(spy).toHaveBeenCalledWith(
      "/api/projects/p1/workflow",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ "X-Tripwire-Role": "pm" }),
      }),
    );
    spy.mockRestore();
  });

  it("does NOT send X-Tripwire-Role when pmMode is false / unset", async () => {
    const spy = mockFetch();
    await workflowApi.get("p1");
    const callArgs = spy.mock.calls[0];
    if (!callArgs) throw new Error("fetch was not called");
    const init = callArgs[1] as RequestInit;
    const headers = (init.headers ?? {}) as Record<string, string>;
    expect(headers["X-Tripwire-Role"]).toBeUndefined();
    spy.mockRestore();
  });
});

describe("queryKeys.workflow + pmMode separation", () => {
  it("PM and non-PM cache entries do not collide", () => {
    // The hook composes the cache key as
    //   [...queryKeys.workflow(pid), { pmMode }]
    // — assert the two variants differ so React Query caches them
    // independently.
    const base = queryKeys.workflow("p1");
    const pmKey = [...base, { pmMode: true }] as const;
    const defaultKey = [...base, { pmMode: false }] as const;
    expect(JSON.stringify(pmKey)).not.toBe(JSON.stringify(defaultKey));
  });
});
