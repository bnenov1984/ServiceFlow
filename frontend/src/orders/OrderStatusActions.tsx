/**
 * Status transition buttons for an order-list row (docs/15 §6.3 OrderRow):
 * the same business-rule dialogs as OrderHeader (§6.6), scoped down to just
 * the status change (no unlock/warranty/archive — those live on the detail
 * screen only).
 */

import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { allowedTransitions, isTerminal, statusName } from "../lib/statusMatrix";
import { ApprovalDialog } from "../order/dialogs/ApprovalDialog";
import { CompletionDialog } from "../order/dialogs/CompletionDialog";
import { ReasonDialog } from "../order/dialogs/ReasonDialog";

const TERMINAL_FAILURE_CODES = new Set(["declined", "unrepairable", "cancelled"]);

type PendingAction = { kind: "reason" | "approval" | "completion"; to: string } | null;

interface AccessoryItem {
  id: string;
  name: string;
  qty: number;
  returned: boolean;
}

export function OrderStatusActions({
  orderId,
  statusCode,
  warrantyDays,
  onChanged,
}: {
  orderId: string;
  statusCode: string;
  // Wave 4 Issue 38: this order's own already-persisted warranty (if any) —
  // same CompletionDialog prefill precedence as OrderHeader's own instance.
  warrantyDays: number | null;
  onChanged: () => void;
}) {
  const { me } = useAuth();
  const pushToast = useToast();
  const [pending, setPending] = useState<PendingAction>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accessories, setAccessories] = useState<AccessoryItem[]>([]);

  const close = () => { setPending(null); setError(null); };

  const runStatusChange = async (body: Record<string, unknown>) => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.post<{ warning: string | null }>(
        `/orders/${orderId}/status`, body,
      );
      onChanged();
      if (result.warning === "skip") pushToast("conflict", t("order.warning_skip"));
      close();
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  const requestTransition = (to: string) => {
    if (TERMINAL_FAILURE_CODES.has(to)) {
      setPending({ kind: "reason", to });
    } else if (statusCode === "waiting_customer" && !isTerminal(to)) {
      setPending({ kind: "approval", to });
    } else if (to === "completed") {
      api.get<AccessoryItem[]>(`/orders/${orderId}/accessories`)
        .then(setAccessories)
        .catch(() => setAccessories([]));
      setPending({ kind: "completion", to });
    } else {
      void runStatusChange({ to });
    }
  };

  const toggleAccessoryReturned = (id: string, returned: boolean) => {
    setAccessories((prev) => prev.map((a) => (a.id === id ? { ...a, returned } : a)));
    void api.patch(`/accessories/${id}`, { returned });
  };

  const buttons = allowedTransitions(statusCode);

  return (
    <>
      <div className="flex flex-wrap gap-1.5">
        {buttons.map(({ code }) => (
          <button
            key={code}
            type="button"
            onClick={() => requestTransition(code)}
            className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs font-medium hover:bg-slate-50 min-h-touch"
          >
            {statusName(code)}
          </button>
        ))}
      </div>

      <ReasonDialog
        open={pending?.kind === "reason"}
        title={t("order.reason_title")}
        requireReason={pending?.kind === "reason" && pending.to !== "unrepairable"}
        onClose={close}
        onConfirm={(reason) => pending && void runStatusChange({ to: pending.to, reason })}
        submitting={submitting}
        error={error}
      />
      <ApprovalDialog
        open={pending?.kind === "approval"}
        onClose={close}
        onConfirm={(channel, amount) =>
          pending &&
          void runStatusChange({ to: pending.to, approval: { approved: true, channel, amount } })
        }
        submitting={submitting}
        error={error}
      />
      <CompletionDialog
        open={pending?.kind === "completion"}
        onClose={close}
        onConfirm={(days) => void runStatusChange({ to: "completed", warranty_days: days })}
        accessories={accessories}
        onToggleReturned={toggleAccessoryReturned}
        submitting={submitting}
        error={error}
        orderWarrantyDays={warrantyDays}
        laborWarrantyDefault={me?.warranty_defaults?.labor_days ?? null}
      />
    </>
  );
}
