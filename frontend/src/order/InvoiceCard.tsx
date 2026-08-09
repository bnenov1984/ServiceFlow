/**
 * InvoiceCard (docs/01 §Invoice): shows whether the order already has an
 * invoice, lets a user create/edit a draft (prefilled from the order's
 * part/labor lines server-side), and — Phase A (docs/ACCOUNTANT_REVIEW.md
 * 'RepairFlow Invoice V1 Freeze' §5) — lets the Owner issue it. Draft totals
 * are backend-authoritative (draft_total, BR-3); once issued, net/vat/gross
 * from the Issue response are the only authoritative totals — this component
 * never recomputes either.
 *
 * The actual draft-editing/Issue and issued-view rendering live in
 * `InvoiceDraftEditor`/`IssuedInvoiceView` (extracted so the invoice-centric
 * `invoices/InvoiceDetailPage` can render the exact same presentation —
 * there is exactly one Invoice UI, reused from two navigation contexts, not
 * two independently maintained ones). This component owns only the
 * order-context chrome: "does this order have an invoice yet" and the
 * inline open/close toggle around the draft editor.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { InvoiceDraftEditor } from "./InvoiceDraftEditor";
import { IssuedInvoiceView } from "./IssuedInvoiceView";
import type { InvoiceOut } from "./invoiceTypes";

export function InvoiceCard({
  orderId, deliveredAt,
}: { orderId: string; deliveredAt: string | null }) {
  const [open, setOpen] = useState(false);

  const { data: invoices, isLoading } = useQuery({
    queryKey: queryKeys.orderInvoices(orderId),
    queryFn: () => api.get<InvoiceOut[]>(`/invoices?order_id=${orderId}`),
  });

  const invoice = invoices?.[0] ?? null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.invoice_section_title")}
      </h3>

      {isLoading && <Skeleton className="h-6 w-32" />}

      {!isLoading && !invoice && (
        <InvoiceCreateButton orderId={orderId} onCreated={() => setOpen(true)} />
      )}

      {!isLoading && invoice?.status === "draft" && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
              {t("order.invoice_status_draft")}
            </span>
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="text-sm text-blue-700 hover:underline"
            >
              {open ? t("order.invoice_close") : t("order.invoice_open")}
            </button>
          </div>
          {open && (
            <InvoiceDraftEditor
              invoiceId={invoice.id}
              orderId={orderId}
              deliveredAt={deliveredAt}
              onClose={() => setOpen(false)}
            />
          )}
        </div>
      )}

      {!isLoading && invoice?.status === "issued" && <IssuedInvoiceView invoiceId={invoice.id} />}
    </div>
  );
}

function InvoiceCreateButton({
  orderId, onCreated,
}: { orderId: string; onCreated: () => void }) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setCreating(true);
    setError(null);
    try {
      await api.post(`/orders/${orderId}/invoices`);
      await queryClient.invalidateQueries({ queryKey: queryKeys.orderInvoices(orderId) });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-slate-400">{t("order.invoice_none")}</p>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <button
        type="button"
        disabled={creating}
        onClick={() => void create()}
        className="self-start rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50 min-h-touch"
      >
        {creating ? t("common.loading") : t("order.invoice_create")}
      </button>
    </div>
  );
}
