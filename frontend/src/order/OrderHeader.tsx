/**
 * OrderHeader (docs/15 §6.5): № + StatusPill + status action buttons (only the
 * allowed ones — server stays the truth, this is UX only per §9) + печат +
 * Owner меню (Отключи/Ново гаранционно/Архивирай).
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { StatusPill } from "../components/StatusPill";
import { useToast } from "../components/Toast";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { allowedTransitions, isTerminal, kindOf, statusName } from "../lib/statusMatrix";
import { ApprovalDialog } from "./dialogs/ApprovalDialog";
import { DeliveryDialog } from "./dialogs/DeliveryDialog";
import { ReasonDialog } from "./dialogs/ReasonDialog";

interface AccessoryItem {
  id: string;
  name: string;
  qty: number;
  returned: boolean;
}

interface OrderHeaderProps {
  orderId: string;
  number: string;
  statusCode: string;
  archived: boolean;
}

const TERMINAL_FAILURE_CODES = new Set(["declined", "unrepairable", "cancelled"]);

type PendingAction =
  | { kind: "reason"; to: string }
  | { kind: "approval"; to: string }
  | { kind: "delivery" }
  | { kind: "unlock" }
  | { kind: "warranty_return" }
  | { kind: "archive" }
  | null;

export function OrderHeader({ orderId, number, statusCode, archived }: OrderHeaderProps) {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const pushToast = useToast();
  const navigate = useNavigate();
  const [pending, setPending] = useState<PendingAction>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Shared cache entry with AccessoriesListSection — a toggle in either place
  // (this dialog or the persistent list) keeps both in sync via invalidation.
  const { data: accessories } = useQuery({
    queryKey: queryKeys.orderAccessories(orderId),
    queryFn: () => api.get<AccessoryItem[]>(`/orders/${orderId}/accessories`),
    enabled: pending?.kind === "delivery",
  });

  const refreshOrder = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.order(orderId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.orderTimeline(orderId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard }),
    ]);

  const close = () => { setPending(null); setError(null); };

  const runStatusChange = async (
    body: Record<string, unknown>,
  ) => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.post<{ warning: string | null }>(
        `/orders/${orderId}/status`, body,
      );
      await refreshOrder();
      if (result.warning === "skip") {
        pushToast("conflict", t("order.warning_skip"));
      } else {
        pushToast("success", t("order.status_changed"));
      }
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
    } else if (to === "delivered") {
      setPending({ kind: "delivery" });
    } else {
      void runStatusChange({ to });
    }
  };

  const toggleAccessoryReturned = async (id: string, returned: boolean) => {
    await api.patch(`/accessories/${id}`, { returned });
    await queryClient.invalidateQueries({ queryKey: queryKeys.orderAccessories(orderId) });
  };

  const runUnlock = async (reason: string) => {
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/orders/${orderId}/unlock`, { reason });
      await refreshOrder();
      pushToast("success", t("order.unlocked"));
      close();
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  const runWarrantyReturn = async (complaint: string) => {
    setSubmitting(true);
    setError(null);
    try {
      const newOrder = await api.post<{ id: string }>(`/orders/${orderId}/warranty-return`, { complaint });
      close();
      navigate(`/orders/${newOrder.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  const runArchive = async () => {
    setSubmitting(true);
    try {
      await api.post(`/orders/${orderId}/archive`);
      await refreshOrder();
      pushToast("success", t("order.archived"));
      close();
    } catch (err) {
      pushToast("error", err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  const buttons = allowedTransitions(statusCode).filter(
    ({ code }) => code !== "cancelled" || me?.is_owner,
  );
  const orderIsTerminal = isTerminal(statusCode);
  const orderIsDelivered = kindOf(statusCode) === "terminal_success";

  return (
    <div className="mb-4 flex flex-wrap items-center gap-3">
      <h1 className="text-2xl font-bold text-slate-900">№ {number}</h1>
      <StatusPill code={statusCode} />

      {!archived && !orderIsTerminal && (
        <div className="flex flex-wrap gap-2">
          {buttons.map(({ code }) => (
            <button
              key={code}
              type="button"
              onClick={() => requestTransition(code)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 min-h-touch"
            >
              {statusName(code)}
            </button>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={() => window.open(`/api/v1/orders/${orderId}/protocol.pdf?type=intake`, "_blank")}
        className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 min-h-touch"
      >
        {t("order.print_protocol")}
      </button>

      {me?.is_owner && (orderIsTerminal || orderIsDelivered) && !archived && (
        <div className="ml-auto flex gap-2">
          {orderIsTerminal && (
            <button
              type="button"
              onClick={() => setPending({ kind: "unlock" })}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 min-h-touch"
            >
              {t("order.unlock")}
            </button>
          )}
          {orderIsDelivered && (
            <button
              type="button"
              onClick={() => setPending({ kind: "warranty_return" })}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 min-h-touch"
            >
              {t("order.warranty_return")}
            </button>
          )}
          {orderIsTerminal && (
            <button
              type="button"
              onClick={() => setPending({ kind: "archive" })}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 min-h-touch"
            >
              {t("order.archive")}
            </button>
          )}
        </div>
      )}

      <ReasonDialog
        open={pending?.kind === "reason"}
        title={t("order.reason_title")}
        requireReason={pending?.kind === "reason" && pending.to !== "unrepairable"}
        onClose={close}
        onConfirm={(reason) => pending?.kind === "reason" && void runStatusChange({ to: pending.to, reason })}
        submitting={submitting}
        error={error}
      />
      <ApprovalDialog
        open={pending?.kind === "approval"}
        onClose={close}
        onConfirm={(channel, amount) =>
          pending?.kind === "approval" &&
          void runStatusChange({
            to: pending.to, approval: { approved: true, channel, amount },
          })
        }
        submitting={submitting}
        error={error}
      />
      <DeliveryDialog
        open={pending?.kind === "delivery"}
        onClose={close}
        onConfirm={(warrantyDays) =>
          void runStatusChange({ to: "delivered", warranty_days: warrantyDays })
        }
        accessories={accessories ?? []}
        onToggleReturned={(id, returned) => void toggleAccessoryReturned(id, returned)}
        submitting={submitting}
        error={error}
      />
      <ReasonDialog
        open={pending?.kind === "unlock"}
        title={t("order.unlock_title")}
        fieldLabel={t("order.unlock_reason_label")}
        requireReason
        onClose={close}
        onConfirm={(reason) => void runUnlock(reason)}
        submitting={submitting}
        error={error}
      />
      <ReasonDialog
        open={pending?.kind === "warranty_return"}
        title={t("order.warranty_return_title")}
        fieldLabel={t("order.warranty_return_complaint_label")}
        requireReason
        onClose={close}
        onConfirm={(complaint) => void runWarrantyReturn(complaint)}
        submitting={submitting}
        error={error}
      />
      <ConfirmDialog
        open={pending?.kind === "archive"}
        title={t("order.archive_title")}
        message={t("order.archive_message")}
        onClose={close}
        onConfirm={() => void runArchive()}
        submitting={submitting}
      />
    </div>
  );
}
