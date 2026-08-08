/**
 * InvoicesPage (central "Фактури" workspace, docs/01 §Invoice): a
 * history/list view over GET /invoices — see that endpoint's own docstring
 * (backend/src/serviceflow/commercial/router.py) for the exact batch-
 * enrichment contract (order_number/customer_name/total) this consumes.
 *
 * Read + navigate only, never a new creation entry point: invoices are still
 * created exclusively from a Service Order's own Invoice section
 * (order/InvoiceCard.tsx) — "Отвори" here navigates to /orders/{order_id}
 * and reuses the existing OrderPage/InvoiceCard rather than a standalone
 * invoice-detail page (deliberately not built in this slice).
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

type StatusFilter = "all" | "draft" | "issued";

interface InvoiceListItem {
  id: string;
  order_id: string;
  order_number: string;
  status: string;
  number: number | null;
  currency: string;
  customer_name: string;
  issued_at: string | null;
  tax_event_date: string | null;
  total: number;
  row_version: number;
}

const PAGE_SIZE = 50;

const STATUS_BADGE_CLASS: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600",
  issued: "bg-green-100 text-green-700",
  annulled: "bg-red-100 text-red-700",
};

// Reuses the exact status labels the per-order InvoiceCard already renders
// (order.invoice_status_draft/issued) — one badge vocabulary, not a second
// one invented for this screen. "annulled" is a real backend status
// (INVOICE_STATUSES) with no UI workflow yet to ever create one, but a row
// must still render sensibly rather than crash if one ever exists.
const STATUS_LABEL_KEY: Record<string, Parameters<typeof t>[0]> = {
  draft: "order.invoice_status_draft",
  issued: "order.invoice_status_issued",
  annulled: "order.invoice_status_annulled",
};

function StatusBadge({ status }: { status: string }) {
  const labelKey = STATUS_LABEL_KEY[status];
  return (
    <span
      className={`whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium ${
        STATUS_BADGE_CLASS[status] ?? "bg-slate-100 text-slate-600"
      }`}
    >
      {labelKey ? t(labelKey) : status}
    </span>
  );
}

function InvoiceRow({ invoice }: { invoice: InvoiceListItem }) {
  const number = invoice.number !== null ? String(invoice.number).padStart(10, "0") : "—";
  const date =
    invoice.status === "issued" && invoice.issued_at
      ? new Date(invoice.issued_at).toLocaleString("bg-BG")
      : "—";

  return (
    <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
      <td className="whitespace-nowrap px-3 py-3 tabular-nums text-slate-900">{number}</td>
      <td className="px-3 py-3 text-slate-700">{invoice.customer_name || "—"}</td>
      <td className="whitespace-nowrap px-3 py-3">
        <Link to={`/orders/${invoice.order_id}`} className="text-blue-700 hover:underline">
          {invoice.order_number}
        </Link>
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-slate-500">{date}</td>
      <td className="whitespace-nowrap px-3 py-3">
        <StatusBadge status={invoice.status} />
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums text-slate-900">
        {invoice.total.toFixed(2)} €
      </td>
      <td className="whitespace-nowrap px-3 py-3">
        <div className="flex items-center gap-3">
          <Link to={`/orders/${invoice.order_id}`} className="text-sm text-blue-700 hover:underline">
            {t("order.invoice_open")}
          </Link>
          {invoice.status === "issued" && (
            <button
              type="button"
              onClick={() => window.open(`/api/v1/invoices/${invoice.id}/invoice.pdf`, "_blank")}
              className="rounded-lg border border-slate-300 px-2 py-1 text-xs font-medium hover:bg-slate-50 min-h-touch"
            >
              {t("order.invoice_pdf")}
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

const STATUS_FILTERS: { value: StatusFilter; labelKey: Parameters<typeof t>[0] }[] = [
  { value: "all", labelKey: "invoices.filter_all" },
  { value: "draft", labelKey: "invoices.filter_draft" },
  { value: "issued", labelKey: "invoices.filter_issued" },
];

export function InvoicesPage() {
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [rows, setRows] = useState<InvoiceListItem[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);

  const statusParam = filter === "all" ? "" : `&status=${filter}`;

  const {
    data: firstPage, isLoading, isError, error, refetch,
  } = useQuery({
    queryKey: queryKeys.invoices(filter),
    queryFn: () => api.get<InvoiceListItem[]>(`/invoices?limit=${PAGE_SIZE}${statusParam}`),
  });

  // Seeds/replaces the accumulated rows whenever a *first* page resolves —
  // i.e. on mount and every filter change (queryKey change). Load More below
  // appends to `rows` directly and deliberately never touches this query.
  useEffect(() => {
    if (firstPage) {
      setRows(firstPage);
      setOffset(firstPage.length);
      setHasMore(firstPage.length === PAGE_SIZE);
    }
  }, [firstPage]);

  const changeFilter = (next: StatusFilter) => {
    if (next === filter) return;
    setFilter(next);
    // Clear synchronously so a stale filter's rows never flash before the
    // new filter's first page resolves (rather than waiting on the effect
    // above, which only fires once `firstPage` itself changes identity).
    setRows([]);
    setOffset(0);
    setHasMore(false);
    setLoadMoreError(null);
  };

  const loadMore = async () => {
    if (loadingMore) return; // guards against a duplicate submit while pending
    setLoadingMore(true);
    setLoadMoreError(null);
    try {
      const next = await api.get<InvoiceListItem[]>(
        `/invoices?limit=${PAGE_SIZE}&offset=${offset}${statusParam}`,
      );
      setRows((prev) => [...prev, ...next]);
      setOffset((prev) => prev + next.length);
      setHasMore(next.length === PAGE_SIZE);
    } catch (err) {
      setLoadMoreError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold text-slate-900">{t("nav.invoices")}</h1>

      <div className="mb-4 flex gap-1 rounded-lg border border-slate-300 p-1" style={{ width: "fit-content" }}>
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            aria-pressed={filter === f.value}
            onClick={() => changeFilter(f.value)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium min-h-touch ${
              filter === f.value ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {t(f.labelKey)}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState
          text={error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal")}
          onRetry={() => void refetch()}
        />
      ) : rows.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th className="px-3 py-2 font-semibold">{t("invoices.column_number")}</th>
                  <th className="px-3 py-2 font-semibold">{t("invoices.column_customer")}</th>
                  <th className="px-3 py-2 font-semibold">{t("invoices.column_order")}</th>
                  <th className="px-3 py-2 font-semibold">{t("invoices.column_date")}</th>
                  <th className="px-3 py-2 font-semibold">{t("invoices.column_status")}</th>
                  <th className="px-3 py-2 text-right font-semibold">{t("invoices.column_total")}</th>
                  <th className="px-3 py-2 font-semibold">{t("invoices.column_actions")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((invoice) => <InvoiceRow key={invoice.id} invoice={invoice} />)}
              </tbody>
            </table>
          </div>

          {loadMoreError && (
            <p role="alert" className="mt-2 text-sm text-red-700">{loadMoreError}</p>
          )}

          {hasMore && (
            <div className="mt-4 flex justify-center">
              <button
                type="button"
                disabled={loadingMore}
                onClick={() => void loadMore()}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50 min-h-touch"
              >
                {loadingMore ? t("common.loading") : t("invoices.load_more")}
              </button>
            </div>
          )}
        </>
      ) : (
        <EmptyState text={`${t("invoices.empty")} ${t("invoices.empty_hint")}`} />
      )}
    </div>
  );
}
