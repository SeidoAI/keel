import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";

import { SourceViewer } from "@/features/workflow/SourceViewer";
import { server } from "../../mocks/server";

function withQueryClient(ui: ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

describe("SourceViewer", () => {
  it("shows the loading placeholder while pending and renders fetched content", async () => {
    server.use(
      http.get("/api/source", () =>
        HttpResponse.json({
          path: "src/foo.py",
          name: "foo.py",
          extension: "py",
          size: 12,
          content: "print('hi')\n",
        }),
      ),
    );

    render(
      withQueryClient(
        <SourceViewer path="src/foo.py" onClose={() => {}} />,
      ),
    );

    expect(screen.getByText("loading source…")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("print('hi')")).toBeInTheDocument();
    });
  });

  it("renders the error placeholder when the fetch fails", async () => {
    server.use(
      http.get("/api/source", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );

    render(
      withQueryClient(
        <SourceViewer path="src/missing.py" onClose={() => {}} />,
      ),
    );

    await waitFor(() => {
      expect(
        screen.getByText(/failed to load source/i),
      ).toBeInTheDocument();
    });
  });

  it("only shows the 'open locally' button when onOpenLocally is provided", () => {
    server.use(http.get("/api/source", () => HttpResponse.json({})));

    const { rerender } = render(
      withQueryClient(
        <SourceViewer path="src/foo.py" onClose={() => {}} />,
      ),
    );
    expect(screen.queryByText(/open locally/i)).toBeNull();

    rerender(
      withQueryClient(
        <SourceViewer
          path="src/foo.py"
          onClose={() => {}}
          onOpenLocally={() => {}}
        />,
      ),
    );
    expect(screen.getByText(/open locally/i)).toBeInTheDocument();
  });

  it("invokes the supplied callbacks when its buttons are clicked", async () => {
    server.use(http.get("/api/source", () => HttpResponse.json({})));

    const onClose = vi.fn();
    const onOpenLocally = vi.fn();

    // Stub navigator.clipboard so the copy-path button doesn't throw
    // in jsdom.
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn() },
    });

    render(
      withQueryClient(
        <SourceViewer
          path="src/foo.py"
          onClose={onClose}
          onOpenLocally={onOpenLocally}
        />,
      ),
    );

    screen.getByLabelText(/close source viewer/i).click();
    expect(onClose).toHaveBeenCalledOnce();

    screen.getByText(/open locally/i).click();
    expect(onOpenLocally).toHaveBeenCalledOnce();

    screen.getByText(/copy path/i).click();
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("src/foo.py");
  });
});
