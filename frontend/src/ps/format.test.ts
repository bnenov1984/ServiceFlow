import { describe, expect, it } from "vitest";
import { deadlineRiskClass, nextActionFor, riskClass, stageState } from "./format";
import type { PsNextAction, PsStage } from "./types";

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

describe("stageState", () => {
  const stages: PsStage[] = [
    { id: "s1", name: "Оглед", category: "work", sort: 0 },
    { id: "s2", name: "Договор", category: "work", sort: 1 },
    { id: "s3", name: "Предаване", category: "delivery", sort: 2 },
  ];
  const current = stages[1]; // "Договор", sort 1

  it("marks the stage matching current_stage.id as current, regardless of sort", () => {
    expect(stageState(stages[1], current)).toBe("current");
  });

  it("marks stages with a lower sort than the current one as completed", () => {
    expect(stageState(stages[0], current)).toBe("completed");
  });

  it("marks stages with a higher sort than the current one as future", () => {
    expect(stageState(stages[2], current)).toBe("future");
  });

  it("treats every stage as future when the assignment has no current stage", () => {
    expect(stageState(stages[0], null)).toBe("future");
    expect(stageState(stages[1], null)).toBe("future");
    expect(stageState(stages[2], null)).toBe("future");
  });

  it("never returns completed for the current stage even if two stages share a sort value", () => {
    const dup: PsStage = { id: "s1-dup", name: "Дубликат", category: "work", sort: 1 };
    expect(stageState(current, current)).toBe("current");
    expect(stageState(dup, current)).toBe("future");
  });

  it("marks exactly one stage as current across a full stage list", () => {
    const states = stages.map((s) => stageState(s, current));
    expect(states.filter((s) => s === "current")).toHaveLength(1);
  });

  it("documents the known approximation: a lower-sort stage reads as completed even if it was actually skipped", () => {
    // Free-form transitions (PS-12 §4) let an assignment jump straight from
    // "Оглед" to "Предаване", never visiting "Договор" at all — this
    // function has no transition history to check, so it still reports
    // "Оглед" and "Договор" as completed purely from their lower sort. See
    // the TODO on stageState(): fix by deriving "completed" from real
    // PSAssignmentStageHistory once a read endpoint exists, not this
    // sort-order approximation.
    const skippedCurrent = stages[2]; // jumped straight to "Предаване"
    expect(stageState(stages[0], skippedCurrent)).toBe("completed");
    expect(stageState(stages[1], skippedCurrent)).toBe("completed");
  });
});
