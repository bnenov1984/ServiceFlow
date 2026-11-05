/**
 * Typed wrapper over the generated transition-matrix.json (docs/15 §9): UX-only
 * — dims/hides forbidden transitions, the server remains the single validator.
 */
import matrix from "../generated/transition-matrix.json";

export type StatusKind =
  | "working" | "waiting" | "ready" | "terminal_success" | "terminal_failure";

interface StatusDef {
  code: string;
  kind: StatusKind;
  name_bg: string;
  sort: number;
}

const STATUSES = matrix.statuses as StatusDef[];
const MATRIX = matrix.matrix as Record<string, Record<string, "ok" | "warn" | "back" | "no">>;

export const ORDERED_STATUSES = [...STATUSES].sort((a, b) => a.sort - b.sort);
export const OPEN_STATUSES = ORDERED_STATUSES.filter(
  (s) => s.kind !== "terminal_success" && s.kind !== "terminal_failure",
);

const byCode = new Map(STATUSES.map((s) => [s.code, s]));

export function statusName(code: string): string {
  return byCode.get(code)?.name_bg ?? code;
}

export function kindOf(code: string): StatusKind {
  return byCode.get(code)?.kind ?? "working";
}

export function isTerminal(code: string): boolean {
  const k = kindOf(code);
  return k === "terminal_success" || k === "terminal_failure";
}

/** Every forward {to: verdict} allowed from `from` — the regular status
 * menu's contents. Excludes "no" and, as of order-workflow-revamp WP-G
 * (Q3), "back" — a backward move is never offered here, only through
 * `backwardTransitions` below's dedicated "Върни към…" action. */
export function allowedTransitions(from: string): { code: string; verdict: "ok" | "warn" }[] {
  const row = MATRIX[from] ?? {};
  return Object.entries(row)
    .filter((entry): entry is [string, "ok" | "warn"] => entry[1] === "ok" || entry[1] === "warn")
    .map(([code, verdict]) => ({ code, verdict }));
}

/** order-workflow-revamp WP-G (Q3/Q3b): every status reachable from `from`
 * only via a backward move (mandatory reason, never the regular menu). */
export function backwardTransitions(from: string): string[] {
  const row = MATRIX[from] ?? {};
  return Object.entries(row).filter(([, verdict]) => verdict === "back").map(([code]) => code);
}
