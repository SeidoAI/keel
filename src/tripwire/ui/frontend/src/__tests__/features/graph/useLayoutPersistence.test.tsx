import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useLayoutPersistence } from "@/features/graph/useLayoutPersistence";

function wrapperWith(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

function mockFetch() {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ id: "n1", layout: { x: 1, y: 2 } }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("useLayoutPersistence", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("debounces persistence calls then PATCHes once per node", async () => {
    const fetchSpy = mockFetch();
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useLayoutPersistence("p1"), {
      wrapper: wrapperWith(qc),
    });

    act(() => {
      result.current.persist({ "user-model": { x: 10, y: 20 } });
      result.current.persist({ "user-model": { x: 11, y: 21 } });
      result.current.persist({ "user-model": { x: 12, y: 22 } });
    });
    expect(fetchSpy).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1), { timeout: 100 });
    const [url, init] = fetchSpy.mock.calls[0] ?? [];
    expect(url).toBe("/api/projects/p1/nodes/user-model/layout");
    expect(init?.method).toBe("PATCH");
    expect(JSON.parse(String(init?.body))).toEqual({ x: 12, y: 22 });
  });

  it("PATCHes one call per distinct node id in a debounced batch", async () => {
    const fetchSpy = mockFetch();
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useLayoutPersistence("p1"), {
      wrapper: wrapperWith(qc),
    });

    act(() => {
      result.current.persist({
        "user-model": { x: 1, y: 1 },
        "auth-flow": { x: 2, y: 2 },
      });
    });
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2), { timeout: 100 });
    const urls = fetchSpy.mock.calls.map((c) => c[0]);
    expect(urls.sort()).toEqual([
      "/api/projects/p1/nodes/auth-flow/layout",
      "/api/projects/p1/nodes/user-model/layout",
    ]);
  });
});
