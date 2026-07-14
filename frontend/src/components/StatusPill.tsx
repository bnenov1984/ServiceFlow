/** Status pill: color communicates urgency, text always carries the meaning
 * too (docs/10 §7 — color is never the sole signal). */

import { kindOf, statusName, type StatusKind } from "../lib/statusMatrix";

const KIND_CLASSES: Record<StatusKind, string> = {
  working: "bg-status-working-bg text-status-working-text",
  waiting: "bg-status-waiting-bg text-status-waiting-text",
  ready: "bg-status-ready-bg text-status-ready-text",
  terminal_success: "bg-status-terminal-success-bg text-status-terminal-success-text",
  terminal_failure: "bg-status-terminal-failure-bg text-status-terminal-failure-text",
};

export function StatusPill({ code }: { code: string }) {
  const kind = kindOf(code);
  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${KIND_CLASSES[kind]}`}>
      {statusName(code)}
    </span>
  );
}
