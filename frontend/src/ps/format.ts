/** Shared badge-color + derived-value helpers for the PropertyFlow dashboard. */

import type { PsDeadlineRisk, PsNextAction } from "./types";

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
