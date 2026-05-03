import { useEffect } from "react";

import type {
  WorkflowRegistry,
  WorkflowRoute,
} from "@/lib/api/endpoints/workflow";
import { TX_H, type LaidOutTransitionRoute } from "./layout";

export interface GateRow {
  kind: "validator" | "prompt-check";
  id: string;
  label: string;
  blurb: string;
}

export function describeGateContents(
  route: WorkflowRoute,
  registry?: WorkflowRegistry,
): GateRow[] {
  const rows: GateRow[] = [];
  const validators = registry?.validators ?? [];
  const promptChecks = registry?.prompt_checks ?? [];
  const valBy = new Map(validators.map((v) => [v.id, v]));
  const pmtBy = new Map(promptChecks.map((p) => [p.id, p]));

  for (const id of route.controls.validators ?? []) {
    const entry = valBy.get(id);
    rows.push({
      kind: "validator",
      id,
      label: id.replace(/^v_/, ""),
      blurb: entry?.description ?? entry?.label ?? "",
    });
  }
  for (const id of route.controls.prompt_checks ?? []) {
    const entry = pmtBy.get(id);
    rows.push({
      kind: "prompt-check",
      id,
      label: id,
      blurb: entry?.description ?? entry?.label ?? "",
    });
  }
  return rows;
}

export interface GatePanelProps {
  tx: LaidOutTransitionRoute;
  chartWidth: number;
  chartHeight: number;
  registry?: WorkflowRegistry;
  onClose: () => void;
}

export function GatePanel({
  tx,
  chartWidth,
  chartHeight,
  registry,
  onClose,
}: GatePanelProps) {
  const rows = describeGateContents(tx.route, registry);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (rows.length === 0) return null;

  const leftPct = (tx.cx / chartWidth) * 100;
  const topPct = ((tx.cy + TX_H / 2 + 10) / chartHeight) * 100;

  return (
    <div
      data-testid={`workflow-gate-panel-${tx.route.id}`}
      role="dialog"
      aria-label={`Gate checks for ${tx.route.label}`}
      style={{
        position: "absolute",
        left: `${leftPct}%`,
        top: `${topPct}%`,
        transform: "translateX(-50%)",
        minWidth: 280,
        maxWidth: 340,
        background: "var(--color-paper)",
        border: "1.5px solid var(--color-gate)",
        boxShadow: "0 14px 30px rgba(26,24,21,0.12)",
        padding: "10px 12px",
        zIndex: 30,
        fontSize: 12,
        color: "var(--color-ink)",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 6,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            letterSpacing: "0.18em",
            color: "var(--color-gate)",
          }}
        >
          GATE · {rows.length} CHECKS
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close gate panel"
          style={{
            cursor: "pointer",
            border: 0,
            background: "none",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--color-ink-3)",
          }}
        >
          ×
        </button>
      </div>
      <div
        style={{
          fontFamily: "var(--font-sans)",
          fontWeight: 600,
          fontSize: 13,
          marginBottom: 8,
        }}
      >
        on {tx.route.label}
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 5,
          maxHeight: 280,
          overflow: "auto",
        }}
      >
        {rows.map((row, i) => (
          <div
            key={`${row.kind}-${row.id}-${i}`}
            style={{
              display: "flex",
              gap: 8,
              padding: "4px 0",
              borderTop: i === 0 ? "none" : "1px dashed var(--color-edge)",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 9,
                color:
                  row.kind === "validator"
                    ? "var(--color-gate)"
                    : "var(--color-info)",
                letterSpacing: "0.04em",
                flexShrink: 0,
                width: 28,
                textTransform: "uppercase",
              }}
            >
              {row.kind === "validator" ? "val" : "pmt"}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10.5,
                  color: "var(--color-ink)",
                }}
              >
                {row.label}
              </div>
              {row.blurb && (
                <div
                  style={{
                    fontFamily: "var(--font-serif)",
                    fontStyle: "italic",
                    fontSize: 11.5,
                    color: "var(--color-ink-2)",
                    marginTop: 1,
                  }}
                >
                  {row.blurb}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
