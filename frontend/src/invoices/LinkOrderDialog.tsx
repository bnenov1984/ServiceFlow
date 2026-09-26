/**
 * Order picker for "Свържи с поръчка" (invoice-order-linking checkpoint 2):
 * lists the invoice's own customer's orders, split into active/history —
 * same two `queryKeys.customerOrders` cache entries `CustomerOrdersSection`
 * already populates on the customer profile page, so this dialog opens
 * instantly from cache when that page was visited first. Deliberately two
 * explicit `state=open`/`state=terminal` fetches rather than relying on
 * `GET /orders`'s `state` param falling through to "all orders" for any
 * other string — that fallthrough has no test coverage backing it as a
 * real contract.
 *
 * Clicking an order links immediately (no secondary confirm) — this
 * endpoint is deliberately the same permission tier as `patch_invoice`
 * (sets a reference, not a legally significant transition), so a single
 * click matches the stakes.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Dialog } from "../components/Dialog";
import { StatusPill } from "../components/StatusPill";
import { useToast } from "../components/Toast";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { InvoiceDetailOut } from "../order/invoiceTypes";
import type { OrderListItem } from "../orders/types";

function OrderSection({
  title, emptyText, orders, disabled, onPick,
}: {
  title: string; emptyText: string; orders: OrderListItem[] | undefined;
  disabled: boolean; onPick: (orderId: string) => void;
}) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {orders && orders.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {orders.map((order) => (
            <li key={order.id}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onPick(order.id)}
                className="flex w-full items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2 text-left hover:bg-slate-50 disabled:opacity-50 min-h-touch"
              >
                <div>
                  <p className="font-medium text-slate-800">№ {order.number}</p>
                  <p className="line-clamp-1 text-sm text-slate-500">{order.complaint}</p>
                </div>
                <StatusPill code={order.status_code} />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-400">{emptyText}</p>
      )}
    </div>
  );
}

export function LinkOrderDialog({
  open, onClose, invoiceId, customerId, onLinked,
}: {
  open: boolean;
  onClose: () => void;
  invoiceId: string;
  customerId: string;
  onLinked: (invoice: InvoiceDetailOut) => void;
}) {
  const queryClient = useQueryClient();
  const pushToast = useToast();
  const [linkingId, setLinkingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: openOrders } = useQuery({
    queryKey: queryKeys.customerOrders(customerId, "open"),
    queryFn: () => api.get<OrderListItem[]>(`/orders?state=open&customer_id=${customerId}`),
    enabled: open,
  });
  const { data: terminalOrders } = useQuery({
    queryKey: queryKeys.customerOrders(customerId, "terminal"),
    queryFn: () => api.get<OrderListItem[]>(`/orders?state=terminal&customer_id=${customerId}`),
    enabled: open,
  });

  const link = async (orderId: string) => {
    if (linkingId) return; // guards against a duplicate submit while pending
    setLinkingId(orderId);
    setError(null);
    try {
      const updated = await api.post<InvoiceDetailOut>(
        `/invoices/${invoiceId}/link-order`,
        { order_id: orderId },
      );
      // Genuinely affected but not locally derivable — link-order emits an
      // invoice_linked timeline event server-side, and the order's own
      // invoice list needs to pick up this invoice; never fabricate either
      // client-side (same reasoning as InvoiceDraftEditor's submitIssue).
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.orderInvoices(orderId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.orderTimeline(orderId) }),
      ]);
      onLinked(updated);
      pushToast("success", t("invoice.linked_to_order_success"));
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setLinkingId(null);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title={t("invoice.link_to_order_title")}>
      <div className="flex flex-col gap-4">
        <OrderSection
          title={t("customer.active_orders")}
          emptyText={t("customer.active_orders_none")}
          orders={openOrders}
          disabled={linkingId !== null}
          onPick={(orderId) => void link(orderId)}
        />
        <OrderSection
          title={t("customer.history")}
          emptyText={t("customer.history_none")}
          orders={terminalOrders}
          disabled={linkingId !== null}
          onPick={(orderId) => void link(orderId)}
        />
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      </div>
    </Dialog>
  );
}
