/**
 * Read-only rendering of an issued Invoice (docs/01 §Invoice, Phase A —
 * docs/ACCOUNTANT_REVIEW.md 'RepairFlow Invoice V1 Freeze' §5): frozen
 * seller/buyer snapshot, lines, and net/vat/gross totals exactly as returned
 * by the backend — never recomputed here. Shared by both `InvoiceCard`
 * (order-centric) and `invoices/InvoiceDetailPage` (invoice-centric) so
 * there is exactly one issued-invoice presentation, not two independently
 * maintained ones.
 *
 * `embedded` (default true) preserves `InvoiceCard`'s exact current look:
 * a top divider plus this component's own status/number/PDF header row,
 * meant to sit below `InvoiceCard`'s own section title. `InvoiceDetailPage`
 * passes `embedded={false}` since it already renders its own page-level
 * header (back link, title, status badge, PDF action) — with `embedded`
 * true there too, the number/status/PDF would render a second time.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { Skeleton } from "../components/States";
import { useToast } from "../components/Toast";
import { StatusBadge } from "../invoices/InvoicesPage";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { apiUrl } from "../lib/apiUrl";
import { queryKeys } from "../lib/queryKeys";
import { AnnulInvoiceDialog } from "./AnnulInvoiceDialog";
import type { InvoiceDetailOut } from "./invoiceTypes";

export function IssuedInvoiceView({
  invoiceId, embedded = true,
}: { invoiceId: string; embedded?: boolean }) {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const pushToast = useToast();
  const [annulOpen, setAnnulOpen] = useState(false);
  const [annulling, setAnnulling] = useState(false);
  const [annulError, setAnnulError] = useState<string | null>(null);

  const { data: invoice, isLoading } = useQuery({
    queryKey: queryKeys.invoice(invoiceId),
    queryFn: () => api.get<InvoiceDetailOut>(`/invoices/${invoiceId}`),
  });

  const submitAnnul = async (reason: string) => {
    if (annulling) return; // guards against a duplicate submit while pending
    setAnnulling(true);
    setAnnulError(null);
    try {
      const annulled = await api.post<InvoiceDetailOut>(`/invoices/${invoiceId}/annul`, { reason });
      queryClient.setQueryData(queryKeys.invoice(invoiceId), annulled);
      if (invoice?.order_id) {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: queryKeys.orderInvoices(invoice.order_id) }),
          queryClient.invalidateQueries({ queryKey: queryKeys.orderTimeline(invoice.order_id) }),
        ]);
      }
      setAnnulOpen(false);
      pushToast("success", t("order.invoice_annulled_success"));
    } catch (err) {
      setAnnulError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setAnnulling(false);
    }
  };

  if (isLoading || !invoice) {
    return <Skeleton className="h-32" />;
  }

  const number = invoice.number !== null ? String(invoice.number).padStart(10, "0") : "";
  const isAnnulled = invoice.status === "annulled";

  return (
    <div className={`flex flex-col gap-3 ${embedded ? "border-t border-slate-100 pt-3" : ""}`}>
      {embedded && (
        <div className="flex items-center justify-between">
          <StatusBadge status={invoice.status} />
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold tabular-nums text-slate-900">
              {t("order.invoice_issued_number")} {number}
            </span>
            <button
              type="button"
              onClick={() => window.open(apiUrl(`/api/v1/invoices/${invoiceId}/invoice.pdf`), "_blank")}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50 min-h-touch"
            >
              {t("order.invoice_pdf")}
            </button>
          </div>
        </div>
      )}

      {isAnnulled && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <p className="font-semibold">{t("order.invoice_annulled_banner")}</p>
          <p className="mt-1">
            {t("order.invoice_annulled_at")} {invoice.annulled_at
              ? new Date(invoice.annulled_at).toLocaleString("bg-BG") : "—"}
          </p>
          <p>{t("order.invoice_annul_reason_display_prefix")} {invoice.annul_reason}</p>
        </div>
      )}

      {!isAnnulled && me?.is_owner && (
        <div>
          <button
            type="button"
            onClick={() => setAnnulOpen(true)}
            className="rounded-lg border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 min-h-touch"
          >
            {t("order.invoice_annul_button")}
          </button>
        </div>
      )}

      <AnnulInvoiceDialog
        open={annulOpen}
        onClose={() => { setAnnulOpen(false); setAnnulError(null); }}
        onConfirm={(reason) => void submitAnnul(reason)}
        submitting={annulling}
        error={annulError}
      />

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {t("order.invoice_issued_at")}
          </dt>
          <dd className="mt-0.5 text-slate-900">
            {invoice.issued_at ? new Date(invoice.issued_at).toLocaleString("bg-BG") : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {t("order.invoice_issue_tax_event_date")}
          </dt>
          <dd className="mt-0.5 text-slate-900">{invoice.tax_event_date ?? "—"}</dd>
        </div>
      </dl>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <h4 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {t("order.invoice_seller")}
          </h4>
          {invoice.seller && (
            <div className="mt-1 text-sm text-slate-700">
              <p>{invoice.seller.name}</p>
              <p>{invoice.seller.address}</p>
              <p>{invoice.seller.eik}</p>
              {invoice.seller.vat_number !== undefined && (
                <p>{t("order.invoice_seller_vat_number_prefix")} {invoice.seller.vat_number}</p>
              )}
            </div>
          )}
        </div>
        <div>
          <h4 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {t("order.invoice_buyer")}
          </h4>
          {invoice.buyer && (
            <div className="mt-1 text-sm text-slate-700">
              <p>{invoice.buyer.name}</p>
              {invoice.buyer.address !== undefined && (
                <p>{t("order.invoice_buyer_address_prefix")} {invoice.buyer.address}</p>
              )}
              {invoice.buyer.eik !== undefined && (
                <p>{t("order.invoice_buyer_eik_prefix")} {invoice.buyer.eik}</p>
              )}
              {invoice.buyer.vat_number !== undefined && (
                <p>{t("order.invoice_buyer_vat_number_prefix")} {invoice.buyer.vat_number}</p>
              )}
            </div>
          )}
        </div>
      </div>

      <ul className="flex flex-col gap-1 text-sm">
        {invoice.lines.map((line) => (
          <li key={line.id} className="flex items-center justify-between gap-2">
            <span className="flex-1 text-slate-700">
              {line.description} × {line.qty}
            </span>
            <span className="tabular-nums text-slate-500">{line.unit_price.toFixed(2)} €</span>
            <span className="w-20 text-right tabular-nums text-slate-900">
              {(line.qty * line.unit_price).toFixed(2)} €
            </span>
          </li>
        ))}
      </ul>

      <dl className="flex flex-col gap-1 border-t border-slate-100 pt-2 text-sm">
        <div className="flex justify-between">
          <dt className="text-slate-500">{t("order.invoice_net")}</dt>
          <dd className="tabular-nums text-slate-900">{(invoice.net ?? 0).toFixed(2)} €</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">
            {t(invoice.seller?.vat_number !== undefined
              ? "order.invoice_vat_charged" : "order.invoice_vat_not_charged")}
          </dt>
          <dd className="tabular-nums text-slate-900">{(invoice.vat ?? 0).toFixed(2)} €</dd>
        </div>
        <div className="flex justify-between text-base font-bold">
          <dt className="text-slate-700">{t("order.invoice_gross")}</dt>
          <dd className="tabular-nums text-slate-900">{(invoice.gross ?? 0).toFixed(2)} €</dd>
        </div>
      </dl>
    </div>
  );
}
