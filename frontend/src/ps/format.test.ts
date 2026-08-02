import { describe, expect, it } from "vitest";
import { deadlineRiskClass, nextActionFor, riskClass } from "./format";
import type { PsNextAction } from "./types";

describe("riskClass", () => {
  it("maps each next-action risk to a distinct badge class", () => {
    expect(riskClass("overdue")).toContain("red");
    expect(riskClass("attention")).toContain("amber");
    expect(riskClass("done")).toContain("slate");
    expect(riskClass("ok")).toContain("green");
  });
});

describe("deadlineRiskClass", () => {
  it("maps breached and critical to the same red badge", () => {
    expect(deadlineRiskClass("breached")).toContain("red");
    expect(deadlineRiskClass("critical")).toContain("red");
  });

  it("maps urgent, attention, normal and none to distinct classes", () => {
    expect(deadlineRiskClass("urgent")).toContain("amber");
    expect(deadlineRiskClass("attention")).toContain("yellow");
    expect(deadlineRiskClass("normal")).toContain("green");
    expect(deadlineRiskClass("none")).toContain("slate");
  });
});

describe("nextActionFor", () => {
  const actions: PsNextAction[] = [
    { id: "a1", assignment_id: "x", title: "Late", owner_user_id: "u1", due_on: "2026-08-01", completed: false, risk: "overdue" },
    { id: "a2", assignment_id: "x", title: "Earliest open", owner_user_id: "u1", due_on: "2026-07-01", completed: false, risk: "attention" },
    { id: "a3", assignment_id: "x", title: "Done earlier", owner_user_id: "u1", due_on: "2026-06-01", completed: true, risk: "done" },
    { id: "a4", assignment_id: "y", title: "Other assignment", owner_user_id: "u1", due_on: "2026-01-01", completed: false, risk: "attention" },
  ];

  it("returns the earliest not-yet-completed action for the given assignment", () => {
    expect(nextActionFor(actions, "x")?.id).toBe("a2");
  });

  it("ignores completed actions and actions belonging to a different assignment", () => {
    expect(nextActionFor(actions, "x")?.id).not.toBe("a3");
    expect(nextActionFor(actions, "z")).toBeNull();
  });
});
