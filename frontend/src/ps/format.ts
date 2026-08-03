/** Shared badge-color + derived-value helpers for the PropertyFlow dashboard. */

import type { PsDeadlineRisk, PsNextAction, PsStage } from "./types";

export function riskClass(risk: PsNextAction["risk"]): string {
  switch (risk) {
    case "overdue":
      return "bg-red-50 text-red-700";
    case "attention":
      return "bg-amber-50 text-amber-700";
    case "done":
      return "bg-slate-100 text-slate-500";
    default:
      return "bg-green-50 text-green-700";
  }
}

export function deadlineRiskClass(risk: PsDeadlineRisk): string {
  switch (risk) {
    case "breached":
    case "critical":
      return "bg-red-50 text-red-700";
    case "urgent":
      return "bg-amber-50 text-amber-700";
    case "attention":
      return "bg-yellow-50 text-yellow-700";
    case "normal":
      return "bg-green-50 text-green-700";
    default:
      return "bg-slate-100 text-slate-500";
  }
}

/** Earliest not-yet-completed action for an assignment — "next action" date
 * shown on engagement cards, derived client-side from the already-fetched
 * next-actions list (no dedicated backend endpoint for this). */
export function nextActionFor(actions: PsNextAction[], assignmentId: string): PsNextAction | null {
  const open = actions
    .filter((a) => a.assignment_id === assignmentId && !a.completed)
    .sort((a, b) => a.due_on.localeCompare(b.due_on));
  return open[0] ?? null;
}

export type StageState = "completed" | "current" | "future";

/** Completed/current/future from the assignment's own copied stage order
 * (`sort`) and its single `current_stage.id` — the only stage facts the API
 * exposes. Stage-transition history (PSAssignmentStageHistory) is recorded
 * on the backend but has no read endpoint, so "completed" here means
 * "earlier in the configured sequence than the current stage," not a
 * verified visit record — free-form transitions (PS-12 §4) can in principle
 * skip a stage entirely. A display simplification of real data, never
 * fabricated state. Exactly one stage is ever "current": the one whose id
 * matches `currentStage.id`, checked before the sort comparison so it can
 * never also read as "completed" even if some future data anomaly gave two
 * stages the same sort value.
 *
 * TODO(stage-history): "completed" here is a visual sequence approximation,
 * not proven history — it can be wrong whenever a transition skips a stage
 * (PS-12 §4 allows jumping to any of the assignment's own stages, not just
 * the next one in order). Once a read endpoint for PSAssignmentStageHistory
 * exists, "completed" must be derived from actual recorded transitions for
 * this assignment, not from `stage.sort < currentStage.sort`. */
export function stageState(stage: PsStage, currentStage: PsStage | null): StageState {
  if (currentStage && stage.id === currentStage.id) return "current";
  if (currentStage && stage.sort < currentStage.sort) return "completed";
  return "future";
}
