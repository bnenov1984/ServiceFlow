/**
 * Design tokens (docs/15 §3) — the single source consumed by tailwind.config.
 * Status colors key off KINDS (docs/02), never off individual status codes.
 */
export const statusKindColors = {
  working: { bg: "#eff6ff", text: "#1d4ed8", solid: "#2563eb" },
  waiting: { bg: "#fffbeb", text: "#b45309", solid: "#d97706" },
  ready: { bg: "#f0fdf4", text: "#15803d", solid: "#16a34a" },
  terminal_success: { bg: "#f1f5f9", text: "#475569", solid: "#64748b" },
  terminal_failure: { bg: "#fef2f2", text: "#991b1b", solid: "#b91c1c" },
} as const;

export type StatusKind = keyof typeof statusKindColors;

export const alertColors = {
  overdue: "#dc2626",
  priorityHigh: "#ea580c",
  info: "#475569",
} as const;

/** Minimum touch target per docs/10 §7. */
export const touchTargetPx = 44;
