/**
 * OrderHeader (docs/15 §6.5): № + StatusPill + status action buttons (only the
 * allowed ones — server stays the truth, this is UX only per §9) + печат +
 * Owner меню (Отключи/Ново гаранционно/Архивирай).
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { StatusPill } from "../components/StatusPill";
import { useToast } from "../components/Toast";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { apiUrl } from "../lib/apiUrl";
import { invalidateOrderViews } from "../lib/orderQueries";
import { queryKeys } from "../lib/queryKeys";
import { allowedTransitions, backwardTransitions, isTerminal, kindOf, statusName } from "../lib/statusMatrix";
import { AcceptDialog } from "./dialogs/AcceptDialog";
import { ApprovalDialog } from "./dialogs/ApprovalDialog";
import { CompletionDialog, type CompletionPaymentInput } from "./dialogs/CompletionDialog";
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
  // Wave 4 Issue 38: this order's own already-persisted warranty (if any),
  // used only to decide CompletionDialog's prefill precedence.
  warrantyDays: number | null;
  // Wave 4 Issue 7: whether a frozen delivery snapshot exists — lets the
  // print action short-circuit to a clear message instead of opening a
  // doomed new tab for a legacy delivered order (or one not delivered yet).
  hasCompletionSnapshot: boolean;
  // order-workflow-revamp WP-G (Q2b): whatever intake already picked, if
  // anything — pre-fills AcceptDialog's technician picker.
  technicianId: string | null;
}

const TERMINAL_FAILURE_CODES = new Set(["declined", "unrepairable", "cancelled"]);

type PendingAction =
  | { kind: "reason"; to: string }
  | { kind: "back"; to: string }
  | { kind: "approval"; to: string }
  | { kind: "accept" }
  | { kind: "completion" }
  | { kind: "unlock" }
  | { kind: "warranty_return" }
  | { kind: "archive" }
  | null;

/** Compact "Промени статус" trigger + dropdown, replacing what used to be
 * every allowed transition rendered as its own always-visible button (up to
 * 8 from "received" alone - 1 normal next step, 4 skip-ahead "warn"
 * transitions, 3 abandon-the-order terminal-failure ones - all with equal
 * visual weight next to the status pill). Same bespoke open/absolute-list
 * idiom as AppShell's AppSwitcher/AccountMenu - no new dependency, no
 * generic Dropdown component. `transitions` and the caller's own owner-only
 * filtering are unchanged; only how they're presented changes. */
function StatusTransitionMenu({
  transitions,
  onSelect,
}: {
  transitions: { code: string; verdict: "ok" | "warn" }[];
  onSelect: (code: string) => void;
}) {
  const [open, setOpen] = useState(false);

  if (transitions.length === 0) return null;

  const normal = transitions.filter(({ code }) => !TERMINAL_FAILURE_CODES.has(code));
  const failure = transitions.filter(({ code }) => TERMINAL_FAILURE_CODES.has(code));

  const pick = (code: string) => {
    setOpen(false);
    onSelect(code);
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 min-h-touch"
      >
        {t("order.change_status_action")} <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <ul
          role="menu"
          className="absolute left-0 top-full z-40 mt-1 w-56 rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {normal.map(({ code, verdict }) => (
            <li key={code} role="none">
              <button
                type="button"
                role="menuitem"
                onClick={() => pick(code)}
                aria-label={
                  verdict === "warn"
                    ? `${statusName(code)} — ${t("order.transition_skip_hint")}`
                    : undefined
                }
                className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 min-h-touch"
              >
                {verdict === "warn" && <span aria-hidden="true">⚠</span>}
                {statusName(code)}
              </button>
            </li>
          ))}
          {failure.length > 0 && (
            <>
              <li role="none" className="my-1 border-t border-slate-100" />
              {failure.map(({ code }) => (
                <li key={code} role="none">
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => pick(code)}
                    className="block w-full px-3 py-2 text-left text-sm text-red-700 hover:bg-red-50 min-h-touch"
                  >
                    {statusName(code)}
                  </button>
                </li>
              ))}
            </>
          )}
        </ul>
      )}
    </div>
  );
}

export function OrderHeader({
  orderId, number, statusCode, archived, warrantyDays, hasCompletionSnapshot, technicianId,
}: OrderHeaderProps) {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const pushToast = useToast();
  const navigate = useNavigate();
  const [pending, setPending] = useState<PendingAction>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Issue 03: not part of the `pending`/dialog state machine above — these
  // two actions fire directly from their own buttons, no confirmation step.
  const [emailingAction, setEmailingAction] = useState<"plain" | "warranty" | null>(null);
  // Confirmed bug: a no-dialog transition (requestTransition's plain "ok"
  // branch) awaits POST -> refreshOrder() -> close() with nothing to stop a
  // user from starting a second action while the first is still in flight -
  // the first action's own trailing close()/setSubmitting(false)/setError()
  // can land *after* the second action already opened its own dialog,
  // silently closing it (observed: a delivery dialog closing itself ~1s
  // after opening, from the *previous* transition's stale cleanup). Every
  // action that can set `pending` bumps this token (openPending below, and
  // each run* at its own start); every run* only touches shared state at
  // the end if no newer action has started since.
  const actionTokenRef = useRef(0);
  const openPending = (action: NonNullable<PendingAction>) => {
    actionTokenRef.current += 1;
    setPending(action);
    // A stale run*'s guarded finally{} legitimately skips its own
    // setSubmitting(false) once superseded (it's not this action's state to
    // clear) — but nothing else was going to clear it either, since this
    // new action's own setSubmitting(true) doesn't fire until its confirm
    // button is actually clicked. Left unreset, that confirm button opens
    // permanently disabled ("Зареждане..." from the moment the dialog
    // appears, never "Предай"/etc.) — reset explicitly here instead.
    setSubmitting(false);
    setError(null);
  };

  // Shared cache entry with AccessoriesListSection — a toggle in either place
  // (this dialog or the persistent list) keeps both in sync via invalidation.
  const { data: accessories } = useQuery({
    queryKey: queryKeys.orderAccessories(orderId),
    queryFn: () => api.get<AccessoryItem[]>(`/orders/${orderId}/accessories`),
    enabled: pending?.kind === "completion",
  });

  const refreshOrder = () => invalidateOrderViews(queryClient, orderId);

  const close = () => { setPending(null); setError(null); };

  const runStatusChange = async (
    body: Record<string, unknown>,
  ) => {
    const token = ++actionTokenRef.current;
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
      if (actionTokenRef.current === token) close();
    } catch (err) {
      if (actionTokenRef.current === token) {
        setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
      }
    } finally {
      if (actionTokenRef.current === token) setSubmitting(false);
    }
  };

  const runComplete = async (
    warrantyDays: number | null, payment: CompletionPaymentInput | null,
  ) => {
    const token = ++actionTokenRef.current;
    setSubmitting(true);
    setError(null);
    try {
      // Payment recording is independent of the status transition (docs/01
      // §ServiceOrder: delivery needs "плащане(ия)", not full settlement) —
      // an open balance never blocks the transition below.
      if (payment) {
        await api.post(`/orders/${orderId}/payments`, payment);
      }
      const result = await api.post<{ warning: string | null }>(
        `/orders/${orderId}/status`, { to: "completed", warranty_days: warrantyDays },
      );
      await refreshOrder();
      if (result.warning === "skip") {
        pushToast("conflict", t("order.warning_skip"));
      } else {
        pushToast("success", t("order.status_changed"));
      }
      if (actionTokenRef.current === token) close();
    } catch (err) {
      if (actionTokenRef.current === token) {
        setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
      }
    } finally {
      if (actionTokenRef.current === token) setSubmitting(false);
    }
  };

  const emailProtocol = async (includeWarranty: boolean) => {
    if (!hasCompletionSnapshot) {
      pushToast("error", t("errors.protocol.delivery_unavailable"));
      return;
    }
    setEmailingAction(includeWarranty ? "warranty" : "plain");
    try {
      await api.post(`/orders/${orderId}/protocol/email`, { include_warranty: includeWarranty });
      pushToast("success", t("order.protocol_emailed"));
    } catch (err) {
      pushToast("error", err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setEmailingAction(null);
    }
  };

  // "completed" is deliberately excluded from `buttons` below (it has its
  // own dedicated primary button, not the generic dropdown), so this never
  // sees `to === "completed"`.
  const requestTransition = (to: string) => {
    if (TERMINAL_FAILURE_CODES.has(to)) {
      openPending({ kind: "reason", to });
    } else if (statusCode === "waiting_customer" && !isTerminal(to)) {
      openPending({ kind: "approval", to });
    } else {
      void runStatusChange({ to });
    }
  };

  const toggleAccessoryReturned = async (id: string, returned: boolean) => {
    await api.patch(`/accessories/${id}`, { returned });
    await queryClient.invalidateQueries({ queryKey: queryKeys.orderAccessories(orderId) });
  };

  const runUnlock = async (reason: string) => {
    const token = ++actionTokenRef.current;
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/orders/${orderId}/unlock`, { reason });
      await refreshOrder();
      pushToast("success", t("order.unlocked"));
      if (actionTokenRef.current === token) close();
    } catch (err) {
      if (actionTokenRef.current === token) {
        setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
      }
    } finally {
      if (actionTokenRef.current === token) setSubmitting(false);
    }
  };

  const runWarrantyReturn = async (complaint: string) => {
    const token = ++actionTokenRef.current;
    setSubmitting(true);
    setError(null);
    try {
      const newOrder = await api.post<{ id: string }>(`/orders/${orderId}/warranty-return`, { complaint });
      if (actionTokenRef.current === token) close();
      navigate(`/orders/${newOrder.id}`);
    } catch (err) {
      if (actionTokenRef.current === token) {
        setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
      }
    } finally {
      if (actionTokenRef.current === token) setSubmitting(false);
    }
  };

  const runArchive = async () => {
    const token = ++actionTokenRef.current;
    setSubmitting(true);
    try {
      await api.post(`/orders/${orderId}/archive`);
      await refreshOrder();
      pushToast("success", t("order.archived"));
      if (actionTokenRef.current === token) close();
    } catch (err) {
      pushToast("error", err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      if (actionTokenRef.current === token) setSubmitting(false);
    }
  };

  // "completed" always has its own dedicated primary button below (PO
  // decision, 2026-09-25 audit) — never offered through the generic
  // dropdown, unlike every other transition.
  const buttons = allowedTransitions(statusCode).filter(
    ({ code }) => (code !== "cancelled" || me?.is_owner) && code !== "completed",
  );
  // order-workflow-revamp WP-G (Q3/Q3b): never in the regular dropdown —
  // only this dedicated "Върни към…" row, each with its own mandatory-
  // reason dialog.
  const backwardTo = backwardTransitions(statusCode);
  const orderIsTerminal = isTerminal(statusCode);
  const orderIsCompleted = kindOf(statusCode) === "terminal_success";
  const orderIsReady = statusCode === "ready";
  // order-workflow-revamp WP-G (Q1/Q2c): НОВА has no regular status
  // dropdown at all — just ПРИЕМИ/ОТКАЖИ (and, Owner-only, Анулирай).
  const orderIsReceived = statusCode === "received";

  return (
    <div className="mb-4 flex flex-wrap items-center gap-3">
      <Link to="/orders" className="text-sm font-medium text-blue-700 hover:underline">
        {t("order.back_to_orders")}
      </Link>
      <h1 className="text-2xl font-bold text-slate-900">№ {number}</h1>
      <StatusPill code={statusCode} />

      {!archived && orderIsReceived && (
        <>
          <button
            type="button"
            onClick={() => openPending({ kind: "accept" })}
            className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 min-h-touch"
          >
            {t("order.accept")}
          </button>
          <button
            type="button"
            onClick={() => openPending({ kind: "reason", to: "declined" })}
            className="rounded-lg border border-red-300 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 min-h-touch"
          >
            {t("order.decline")}
          </button>
          {me?.is_owner && (
            <button
              type="button"
              onClick={() => openPending({ kind: "reason", to: "cancelled" })}
              className="text-sm font-medium text-slate-500 hover:underline"
            >
              {t("order.cancel_order")}
            </button>
          )}
        </>
      )}

      {!archived && !orderIsTerminal && !orderIsReceived && (
        <StatusTransitionMenu transitions={buttons} onSelect={requestTransition} />
      )}

      {!archived && !orderIsTerminal && backwardTo.map((to) => (
        <button
          key={to}
          type="button"
          onClick={() => openPending({ kind: "back", to })}
          className="rounded-lg border border-amber-300 px-3 py-2 text-sm font-medium text-amber-700 hover:bg-amber-50 min-h-touch"
        >
          ↩ {t("order.back_to_action", { status: statusName(to) })}
        </button>
      ))}

      {!archived && orderIsReady && (
        <button
          type="button"
          onClick={() => openPending({ kind: "completion" })}
          className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 min-h-touch"
        >
          {t("order.complete_order")}
        </button>
      )}

      <button
        type="button"
        onClick={() => window.open(apiUrl(`/api/v1/orders/${orderId}/protocol.pdf?type=intake`), "_blank")}
        className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 min-h-touch"
      >
        {t("order.print_protocol")}
      </button>

      {orderIsCompleted && (
        <>
          <button
            type="button"
            onClick={() => {
              if (hasCompletionSnapshot) {
                window.open(apiUrl(`/api/v1/orders/${orderId}/protocol.pdf?type=delivery`), "_blank");
              } else {
                pushToast("error", t("errors.protocol.delivery_unavailable"));
              }
            }}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 min-h-touch"
          >
            {t("order.print_delivery_protocol")}
          </button>
          <button
            type="button"
            disabled={emailingAction !== null}
            onClick={() => void emailProtocol(false)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50 min-h-touch"
          >
            {emailingAction === "plain" ? t("common.loading") : t("order.email_protocol")}
          </button>
          <button
            type="button"
            disabled={emailingAction !== null}
            onClick={() => void emailProtocol(true)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50 min-h-touch"
          >
            {emailingAction === "warranty"
              ? t("common.loading")
              : t("order.email_protocol_with_warranty")}
          </button>
        </>
      )}

      {me?.is_owner && (orderIsTerminal || orderIsCompleted) && !archived && (
        <div className="ml-auto flex gap-2">
          {orderIsTerminal && (
            <button
              type="button"
              onClick={() => openPending({ kind: "unlock" })}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 min-h-touch"
            >
              {t("order.unlock")}
            </button>
          )}
          {orderIsCompleted && (
            <button
              type="button"
              onClick={() => openPending({ kind: "warranty_return" })}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 min-h-touch"
            >
              {t("order.warranty_return")}
            </button>
          )}
          {orderIsTerminal && (
            <button
              type="button"
              onClick={() => openPending({ kind: "archive" })}
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
      <ReasonDialog
        open={pending?.kind === "back"}
        title={
          pending?.kind === "back"
            ? t("order.back_to_action", { status: statusName(pending.to) })
            : ""
        }
        requireReason
        onClose={close}
        onConfirm={(reason) => pending?.kind === "back" && void runStatusChange({ to: pending.to, reason })}
        submitting={submitting}
        error={error}
      />
      <AcceptDialog
        open={pending?.kind === "accept"}
        currentTechnicianId={technicianId}
        onClose={close}
        onConfirm={(id) => void runStatusChange({ to: "diagnostics", technician_id: id })}
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
      <CompletionDialog
        open={pending?.kind === "completion"}
        onClose={close}
        onConfirm={(days, payment) => void runComplete(days, payment)}
        accessories={accessories ?? []}
        onToggleReturned={(id, returned) => void toggleAccessoryReturned(id, returned)}
        submitting={submitting}
        error={error}
        orderWarrantyDays={warrantyDays}
        laborWarrantyDefault={me?.warranty_defaults?.labor_days ?? null}
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
