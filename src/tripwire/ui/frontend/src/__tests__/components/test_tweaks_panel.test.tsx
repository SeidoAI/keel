import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { TweaksPanel } from "@/components/tweaks/TweaksPanel";
import { TWEAK_DEFAULTS, TweaksProvider } from "@/components/tweaks/TweaksContext";

const STORAGE_KEY = "tripwire.tweaks.v1";

describe("TweaksPanel", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("style");
  });
  afterEach(() => {
    cleanup();
    localStorage.clear();
  });

  it("does not render the panel by default", () => {
    render(
      <TweaksProvider>
        <TweaksPanel />
      </TweaksProvider>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens when defaultOpen is true", () => {
    render(
      <TweaksProvider>
        <TweaksPanel defaultOpen />
      </TweaksProvider>,
    );
    expect(screen.getByRole("dialog", { name: /tweaks/i })).toBeInTheDocument();
  });

  it("renders the six tweak dimensions when open", () => {
    render(
      <TweaksProvider>
        <TweaksPanel defaultOpen />
      </TweaksProvider>,
    );
    expect(screen.getByLabelText(/paper warmth/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/rule colour/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/density/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/stamp shape/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/serif family/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/mono family/i)).toBeInTheDocument();
  });

  it("persists changed settings to localStorage under tripwire.tweaks.v1", async () => {
    const user = userEvent.setup();
    render(
      <TweaksProvider>
        <TweaksPanel defaultOpen />
      </TweaksProvider>,
    );
    await user.selectOptions(screen.getByLabelText(/paper warmth/i), "linen");
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(stored.paperWarmth).toBe("linen");
  });

  it("loads stored settings on mount", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ ...TWEAK_DEFAULTS, ruleColour: "ochre" }),
    );
    render(
      <TweaksProvider>
        <TweaksPanel defaultOpen />
      </TweaksProvider>,
    );
    expect(screen.getByLabelText(/rule colour/i)).toHaveValue("ochre");
  });

  it("writes a CSS variable on the document root when the rule colour changes", async () => {
    const user = userEvent.setup();
    render(
      <TweaksProvider>
        <TweaksPanel defaultOpen />
      </TweaksProvider>,
    );
    await user.selectOptions(screen.getByLabelText(/rule colour/i), "indigo");
    // The Tweaks panel pushes the chosen value into the CSS custom
    // property tree on <html>; CSS-only consumers (like the
    // LifecycleWire's `stroke="var(--color-rule)"`) pick it up
    // automatically without React re-renders.
    expect(document.documentElement.style.getPropertyValue("--color-rule")).not.toBe("");
  });
});
