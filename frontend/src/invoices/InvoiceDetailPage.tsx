/**
 * InvoiceDetailPage (docs/01 §Invoice): the invoice-centric counterpart to
 * `order/InvoiceCard.tsx`'s order-centric view — same backend Invoice, same
 * `queryKeys.invoice(id)` cache, same `InvoiceDraftEditor`/`IssuedInvoiceView`
 * presentation components, reached via a different navigation path
 * (invoices/InvoicesPage.tsx's "Отвори", or a direct/bookmarked URL).
 *
 * This page owns only: the route param, the Invoice detail fetch, loading/
 * error/not-found chrome, and the page-level header (back link, title,
 * status badge, PDF action for issued invoices, originating-order link). All
 * draft-editing/Issue and issued-view rendering is delegated — no Invoice
 * business logic lives here. Both `InvoiceDraftEditor`/`IssuedInvoiceView`
 * are rendered with `embedded={false}`: their own top divider and (for
 * IssuedInvoiceView) internal number/status/PDF header row are meant for
 * sitting below `InvoiceCard`'s own title — with this page's own header
 * already showing that same information, `embedded` suppresses the
 * duplication rather than rendering it twice.
 *
 * order_number is resolved via a second query against the already-existing
 * GET /orders/{id} (the same endpoint/queryKey OrderPage itself uses) rather
 * than expanding InvoiceDetailOut solely for this cosmetic display — see
 * this task's own read-first audit for why that was preferred.
 *
 * After a successful Issue while viewing this page, the shared
 * queryKeys.invoice(id) cache (written by InvoiceDraftEditor's submitIssue)
 * flips this page's own query to the issued response — the page stays on
 * /invoices/{id} and re-renders as IssuedInvoiceView, no redirect.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { InvoiceDraftEditor } from "../order/InvoiceDraftEditor";
import { IssuedInvoiceView } from "../order/IssuedInvoiceView";
import type { InvoiceDetailOut } from "../order/invoiceTypes";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { apiUrl } from "../lib/apiUrl";
import { queryKeys } from "../lib/queryKeys";
import { LinkOrderDialog } from "./LinkOrderDialog";
import { StatusBadge } from "./InvoicesPage";

interface OrderSummary {
  id: string;
  number: string;
  completed_at: string | null;
  customer_id: string;
}

export function InvoiceDetailPage() {
  const { invoiceId } = useParams<{ invoiceId: string }>();
  const id = invoiceId!;
  const queryClient = useQueryClient();
  const [linkOpen, setLinkOpen] = useState(false);

  const {
    data: invoice, isLoading, isError, error, refetch,
  } = useQuery({
    queryKey: queryKeys.invoice(id),
    queryFn: () => api.get<InvoiceDetailOut>(`/invoices/${id}`),
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });

  // Wave 6 Issue 30 — a manual invoice has no order_id at all; this query
  // stays disabled for one, and every order-derived value below falls back
  // to the invoice's own customer_id/null instead.
  const { data: order } = useQuery({
    queryKey: queryKeys.order(invoice?.order_id ?? ""),
    queryFn: () => api.get<OrderSummary>(`/orders/${invoice!.order_id}`),
    enabled: !!invoice?.order_id,
  });

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (isError || !invoice) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <EmptyState
          text={t("errors.invoices.not_found")}
          action={
            <Link to="/invoices" className="text-sm font-medium text-blue-700 hover:underline">
              {t("nav.invoices")}
            </Link>
          }
        />
      );
    }
    return (
      <ErrorState
        text={error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal")}
        onRetry={() => void refetch()}
      />
    );
  }

  const number = invoice.number !== null ? String(invoice.number).padStart(10, "0") : null;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/invoices" className="text-sm font-medium text-blue-700 hover:underline">
          {t("invoice.back_to_invoices")}
        </Link>
        <h1 className="text-2xl font-bold text-slate-900">
          {number ? `${t("order.invoice_issued_number")} ${number}` : t("order.invoice_section_title")}
        </h1>
        <StatusBadge status={invoice.status} />
        {(invoice.status === "issued" || invoice.status === "annulled") && (
          <button
            type="button"
            onClick={() => window.open(apiUrl(`/api/v1/invoices/${invoice.id}/invoice.pdf`), "_blank")}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50 min-h-touch"
          >
            {t("order.invoice_pdf")}
          </button>
        )}
      </div>

      {invoice.order_id !== null ? (
        <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {t("invoice.order_label")}
          </span>
          <div className="mt-1">
            {order ? (
              <Link
                to={`/orders/${invoice.order_id}`}
                className="font-medium text-blue-700 hover:underline"
              >
                {order.number}
              </Link>
            ) : (
              <Skeleton className="h-4 w-20" />
            )}
          </div>
        </div>
      ) : (
        invoice.customer_id !== null && (
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
            <button
              type="button"
              onClick={() => setLinkOpen(true)}
              className="font-medium text-blue-700 hover:underline"
            >
              {t("invoice.link_to_order_action")}
            </button>
          </div>
        )
      )}

      {linkOpen && invoice.customer_id !== null && (
        <LinkOrderDialog
          open={linkOpen}
          onClose={() => setLinkOpen(false)}
          invoiceId={invoice.id}
          customerId={invoice.customer_id}
          onLinked={(updated) => queryClient.setQueryData(queryKeys.invoice(id), updated)}
        />
      )}

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        {invoice.status === "draft" ? (
          <InvoiceDraftEditor
            invoiceId={invoice.id}
            orderId={invoice.order_id ?? undefined}
            completedAt={order?.completed_at ?? null}
            customerId={order?.customer_id ?? invoice.customer_id ?? undefined}
            embedded={false}
          />
        ) : (
          <IssuedInvoiceView invoiceId={invoice.id} embedded={false} />
        )}
      </div>
    </div>
  );
}
