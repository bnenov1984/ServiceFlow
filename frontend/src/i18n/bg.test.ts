import { describe, expect, it } from "vitest";
import { bg, t } from "./bg";

describe("t()", () => {
  it("renders params", () => {
    expect(t("search.empty", { q: "иван" })).toBe("Нищо не е намерено за „иван“.");
  });

  it("falls back to generic error for unknown backend keys (docs/15 §5.1)", () => {
    expect(t("errors.something.brand_new")).toBe(bg["errors.internal"]);
  });

  it("passes through non-error unknown keys verbatim for debuggability", () => {
    expect(t("nav.dashboard")).toBe("Табло");
  });

  it("brands the shell as Business OS, not ServiceFlow (25.07.2026 rebrand)", () => {
    expect(t("app.name")).toBe("Business OS");
    expect(t("app.repairflow")).toBe("RepairFlow");
    expect(t("app.propertyflow")).toBe("PropertyFlow");
    expect(t("ps.title")).toBe("PropertyFlow");
  });

  it("keeps unmatched placeholders visible instead of dropping them", () => {
    expect(t("search.empty", {})).toContain("{q}");
  });
});
