/**
 * InvoiceCard (docs/01 §Invoice): lists every invoice belonging to this
 * order (Wave 6 Issue 30/35 — `ServiceOrder 1──* Invoice` is already the
 * real cardinality, docs/01's relationships section; an order may have more
 * than one draft/issued/annulled invoice, e.g. a case-A annul followed by a
 * manually-created replacement, or simply two independent invoices) and
 * lets a user create/edit a draft (prefilled from the order's part/labor
 * lines server-side) plus — Phase A (docs/ACCOUNTANT_REVIEW.md 'RepairFlow
 * Invoice V1 Freeze' §5) — issue it. Draft totals are backend-authoritative
 * (draft_total, BR-3); once issued, net/vat/gross from the Issue response
 * are the only authoritative totals — this component never recomputes
 * either.
 *
 * The actual draft-editing/Issue and issued-or-annulled-view rendering live
 * in `InvoiceDraftEditor`/`IssuedInvoiceView` (extracted so the
 * invoice-centric `invoices/InvoiceDetailPage` can render the exact same
 * presentation — there is exactly one Invoice UI, reused from two
 * navigation contexts, not two independently maintained ones). This
 * component owns only the order-context chrome: the list of this order's
 * invoices and the inline open/close toggle around each draft's editor.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Skeleton } from "../components/States";
import { StatusBadge } from "../invoices/InvoicesPage";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { InvoiceDraftEditor } from "./InvoiceDraftEditor";
import { IssuedInvoiceView } from "./IssuedInvoiceView";
import type { InvoiceOut } from "./invoiceTypes";

export function InvoiceCard({
  orderId, deliveredAt, customerId,
}: { orderId: string; deliveredAt: string | null; customerId?: string }) {
  const [justCreatedId, setJustCreatedId] = useState<string | null>(null);

  const { data: invoices, isLoading } = useQuery({
    queryKey: queryKeys.orderInvoices(orderId),
    queryFn: () => api.get<InvoiceOut[]>(`/invoices?order_id=${orderId}`),
  });

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.invoice_section_title")}
      </h3>

      {isLoading && <Skeleton className="h-6 w-32" />}

      {!isLoading && (
        <div className="flex flex-col gap-3">
          {(invoices ?? []).length === 0 && (
            <p className="text-sm text-slate-400">{t("order.invoice_none")}</p>
          )}
          {(invoices ?? []).map((invoice, index) => (
            <InvoiceEntry
              key={invoice.id}
              invoice={invoice}
              orderId={orderId}
              deliveredAt={deliveredAt}
              customerId={customerId}
              defaultOpen={invoice.id === justCreatedId}
              divider={index > 0}
            />
          ))}
          <InvoiceCreateButton orderId={orderId} onCreated={setJustCreatedId} />
        </div>
      )}
    </div>
  );
}

function InvoiceEntry({
  invoice, orderId, deliveredAt, customerId, defaultOpen, divider,
}: {
  invoice: InvoiceOut; orderId: string; deliveredAt: string | null; customerId?: string;
  defaultOpen: boolean; divider: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  if (invoice.status !== "draft") {
    return (
      <div className={divider ? "border-t border-slate-100 pt-3" : ""}>
        <IssuedInvoiceView invoiceId={invoice.id} />
      </div>
    );
  }

  return (
    <div className={`flex flex-col gap-2 ${divider ? "border-t border-slate-100 pt-3" : ""}`}>
      <div className="flex items-center justify-between">
        <StatusBadge status="draft" />
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
          customerId={customerId}
          onClose={() => setOpen(false)}
        />
      )}
    </div>
  );
}

function InvoiceCreateButton({
  orderId, onCreated,
}: { orderId: string; onCreated: (invoiceId: string) => void }) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setCreating(true);
    setError(null);
    try {
      const invoice = await api.post<InvoiceOut>(`/orders/${orderId}/invoices`);
      await queryClient.invalidateQueries({ queryKey: queryKeys.orderInvoices(orderId) });
      onCreated(invoice.id);
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
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
