/**
 * InvoiceCard (docs/01 §Invoice): shows whether the order already has an
 * invoice, lets a user create/edit a draft (prefilled from the order's
 * part/labor lines server-side), and — Phase A (docs/ACCOUNTANT_REVIEW.md
 * 'RepairFlow Invoice V1 Freeze' §5) — lets the Owner issue it. Draft totals
 * are backend-authoritative (draft_total, BR-3); once issued, net/vat/gross
 * from the Issue response are the only authoritative totals — this component
 * never recomputes either.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { InvoiceIssueDialog, type IssueErrorInfo } from "./InvoiceIssueDialog";

interface InvoiceOut {
  id: string;
  order_id: string;
  status: string;
  number: number | null;
  currency: string;
  row_version: number;
}

interface InvoiceLineOut {
  id: string;
  description: string;
  qty: number;
  unit_price: number;
  vat_rate: number | null;
  source: string;
}

interface SellerSnapshot {
  name: string;
  address: string;
  eik: string;
  vat_registered: boolean;
}

interface BuyerSnapshot {
  name: string;
}

interface InvoiceDetailOut extends InvoiceOut {
  lines: InvoiceLineOut[];
  draft_total: number;
  tax_event_date: string | null;
  issued_at: string | null;
  seller: SellerSnapshot | null;
  buyer: BuyerSnapshot | null;
  vat_mode: string | null;
  net: number | null;
  vat: number | null;
  gross: number | null;
}

interface LineDraft {
  description: string;
  qty: string;
  unit_price: string;
  source: string;
}

const SOURCE_LABEL: Record<string, Parameters<typeof t>[0]> = {
  labor: "order.invoice_line_source_labor",
  part: "order.invoice_line_source_part",
  manual: "order.invoice_line_source_manual",
  adjustment: "order.invoice_line_source_adjustment",
};

function toLineDraft(line: InvoiceLineOut): LineDraft {
  return {
    description: line.description,
    qty: String(line.qty),
    unit_price: line.unit_price.toFixed(2),
    source: line.source,
  };
}

function todayLocalISODate(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Client-side convenience default only — the user sees and can edit it
 * before confirming (docs/ACCOUNTANT_REVIEW.md D1: never backend-derived,
 * and never silently sent unedited). Sliced directly from the ISO string,
 * never routed through a Date object: delivered_at is a UTC timestamp, and
 * parsing+reformatting it through local Date arithmetic risks rendering the
 * wrong calendar day near a local midnight boundary. */
function defaultTaxEventDate(deliveredAt: string | null): string {
  return deliveredAt ? deliveredAt.slice(0, 10) : todayLocalISODate();
}

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

function InvoiceDraftEditor({
  invoiceId, orderId, deliveredAt, onClose,
}: { invoiceId: string; orderId: string; deliveredAt: string | null; onClose: () => void }) {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const pushToast = useToast();
  const [lines, setLines] = useState<LineDraft[] | null>(null);
  const [newDescription, setNewDescription] = useState("");
  const [newQty, setNewQty] = useState("1");
  const [newPrice, setNewPrice] = useState("");
  const [newSource, setNewSource] = useState<"manual" | "adjustment">("manual");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [issueOpen, setIssueOpen] = useState(false);
  const [issuing, setIssuing] = useState(false);
  const [issueError, setIssueError] = useState<IssueErrorInfo | null>(null);

  const { data: invoice, isLoading } = useQuery({
    queryKey: queryKeys.invoice(invoiceId),
    queryFn: () => api.get<InvoiceDetailOut>(`/invoices/${invoiceId}`),
  });

  // Seed the local edit buffer once from the fetched draft — re-seeded every
  // time this editor mounts (i.e. every re-open), so closing and reopening
  // always starts from the last *saved* state, never stale unsaved edits.
  useEffect(() => {
    if (invoice && lines === null) setLines(invoice.lines.map(toLineDraft));
  }, [invoice, lines]);

  const removeLine = (index: number) => {
    setLines((prev) => (prev ? prev.filter((_, i) => i !== index) : prev));
  };

  const updateLine = (index: number, patch: Partial<LineDraft>) => {
    setLines((prev) =>
      prev ? prev.map((line, i) => (i === index ? { ...line, ...patch } : line)) : prev,
    );
  };

  const addLine = () => {
    if (!newDescription.trim()) return;
    setLines((prev) => [
      ...(prev ?? []),
      {
        description: newDescription.trim(),
        qty: newQty.trim() || "1",
        unit_price: newPrice.trim() || "0",
        source: newSource,
      },
    ]);
    setNewDescription("");
    setNewQty("1");
    setNewPrice("");
  };

  const save = async () => {
    if (!lines) return;
    setSaving(true);
    setError(null);
    try {
      await api.patch(`/invoices/${invoiceId}`, {
        lines: lines.map((line) => ({
          description: line.description,
          qty: line.qty.trim() ? Number(line.qty) : 1,
          unit_price: line.unit_price.trim() ? Number(line.unit_price) : 0,
          source: line.source,
        })),
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.invoice(invoiceId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.orderInvoices(orderId) }),
      ]);
      pushToast("success", t("order.invoice_saved"));
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSaving(false);
    }
  };

  const submitIssue = async (taxEventDate: string) => {
    if (issuing) return; // guards against a duplicate submit while pending
    setIssuing(true);
    setIssueError(null);
    try {
      const issued = await api.post<InvoiceDetailOut>(`/invoices/${invoiceId}/issue`, {
        tax_event_date: taxEventDate,
      });
      // Seed both affected caches directly from the response — no extra GET.
      queryClient.setQueryData(queryKeys.invoice(invoiceId), issued);
      queryClient.setQueryData<InvoiceOut[]>(queryKeys.orderInvoices(orderId), (prev) =>
        prev
          ? prev.map((inv) =>
              inv.id === invoiceId ? { ...inv, status: issued.status, number: issued.number } : inv,
            )
          : prev,
      );
      // Genuinely affected but not locally derivable — Issue publishes a new
      // invoice_issued event server-side; never fabricate it client-side.
      await queryClient.invalidateQueries({ queryKey: queryKeys.orderTimeline(orderId) });
      setIssueOpen(false);
      pushToast("success", t("order.invoice_issued_success"));
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.messageKey === "errors.invoices.not_draft") {
          // Someone else issued it concurrently — reflect the real state
          // (which the list-cache patch above did not anticipate) rather
          // than argue with a stale local draft.
          await queryClient.invalidateQueries({ queryKey: queryKeys.orderInvoices(orderId) });
          setIssueOpen(false);
          return;
        }
        setIssueError({ message: t(err.messageKey, err.params), key: err.messageKey });
      } else {
        setIssueError({ message: t("errors.internal"), key: "" });
      }
    } finally {
      setIssuing(false);
    }
  };

  if (isLoading || !invoice || lines === null) {
    return <Skeleton className="h-24" />;
  }

  const isEmpty = lines.length === 0;

  return (
    <div className="flex flex-col gap-3 border-t border-slate-100 pt-3">
      <ul className="flex flex-col gap-2">
        {lines.map((line, index) => (
          <li key={index} className="flex items-center gap-2 text-sm">
            <input
              type="text"
              value={line.description}
              placeholder={t("order.invoice_line_description_placeholder")}
              onChange={(e) => updateLine(index, { description: e.target.value })}
              className="flex-1 rounded-lg border border-slate-300 px-2 py-1 min-h-touch"
            />
            <input
              type="number" min={1} value={line.qty}
              aria-label={t("order.invoice_line_qty")}
              onChange={(e) => updateLine(index, { qty: e.target.value })}
              className="w-16 rounded-lg border border-slate-300 px-2 py-1 min-h-touch"
            />
            <input
              type="number" min={0} step="0.01" value={line.unit_price}
              aria-label={t("order.invoice_line_price")}
              onChange={(e) => updateLine(index, { unit_price: e.target.value })}
              className="w-24 rounded-lg border border-slate-300 px-2 py-1 min-h-touch"
            />
            <span className="w-20 text-right tabular-nums text-slate-500">
              {((Number(line.qty) || 0) * (Number(line.unit_price) || 0)).toFixed(2)} €
            </span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
              {t(SOURCE_LABEL[line.source] ?? "order.invoice_line_source_manual")}
            </span>
            <button
              type="button"
              onClick={() => removeLine(index)}
              aria-label={t("order.invoice_line_remove")}
              className="text-slate-400 hover:text-red-700"
            >
              ✕
            </button>
          </li>
        ))}
        {lines.length === 0 && (
          <p className="text-sm text-slate-400">{t("order.invoice_lines_none")}</p>
        )}
      </ul>

      <div className="flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 p-2">
        <input
          type="text" value={newDescription} onChange={(e) => setNewDescription(e.target.value)}
          placeholder={t("order.invoice_line_description_placeholder")}
          className="flex-1 rounded-lg border border-slate-300 px-2 py-1 text-sm min-h-touch"
        />
        <input
          type="number" min={1} value={newQty} onChange={(e) => setNewQty(e.target.value)}
          aria-label={t("order.invoice_line_qty")}
          className="w-16 rounded-lg border border-slate-300 px-2 py-1 text-sm min-h-touch"
        />
        <input
          type="number" min={0} step="0.01" value={newPrice}
          onChange={(e) => setNewPrice(e.target.value)}
          aria-label={t("order.invoice_line_price")}
          placeholder="€"
          className="w-20 rounded-lg border border-slate-300 px-2 py-1 text-sm min-h-touch"
        />
        <div className="flex gap-1">
          {(["manual", "adjustment"] as const).map((src) => (
            <button
              key={src}
              type="button"
              onClick={() => setNewSource(src)}
              aria-pressed={newSource === src}
              className={`rounded-full border px-2 py-1 text-xs font-medium min-h-touch ${
                newSource === src
                  ? "border-blue-600 bg-blue-600 text-white"
                  : "border-slate-300 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {t(SOURCE_LABEL[src])}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={addLine}
          className="rounded-lg border border-slate-300 px-3 py-1 text-sm hover:bg-white min-h-touch"
        >
          {t("intake.accessory_add")}
        </button>
      </div>

      <div className="flex items-center justify-between border-t border-slate-100 pt-2">
        <span className="text-sm font-medium text-slate-700">{t("order.invoice_total")}</span>
        <span className="text-lg font-bold tabular-nums text-slate-900">
          {invoice.draft_total.toFixed(2)} €
        </span>
      </div>

      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={saving}
          onClick={() => void save()}
          className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
        >
          {saving ? t("common.loading") : t("common.save")}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch"
        >
          {t("common.close")}
        </button>
        {me?.is_owner && (
          <button
            type="button"
            disabled={isEmpty}
            title={isEmpty ? t("order.invoice_issue_empty_hint") : undefined}
            onClick={() => setIssueOpen(true)}
            className="ml-auto rounded-lg border border-blue-600 px-3 py-1.5 text-sm font-semibold text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-300 min-h-touch"
          >
            {t("order.invoice_button")}
          </button>
        )}
      </div>

      {issueOpen && (
        <InvoiceIssueDialog
          open={issueOpen}
          onClose={() => { setIssueOpen(false); setIssueError(null); }}
          onConfirm={(date) => void submitIssue(date)}
          submitting={issuing}
          error={issueError}
          draftTotal={invoice.draft_total}
          defaultTaxEventDate={defaultTaxEventDate(deliveredAt)}
        />
      )}
    </div>
  );
}

function IssuedInvoiceView({ invoiceId }: { invoiceId: string }) {
  const { data: invoice, isLoading } = useQuery({
    queryKey: queryKeys.invoice(invoiceId),
    queryFn: () => api.get<InvoiceDetailOut>(`/invoices/${invoiceId}`),
  });

  if (isLoading || !invoice) {
    return <Skeleton className="h-32" />;
  }

  const number = invoice.number !== null ? String(invoice.number).padStart(10, "0") : "";

  return (
    <div className="flex flex-col gap-3 border-t border-slate-100 pt-3">
      <div className="flex items-center justify-between">
        <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700">
          {t("order.invoice_status_issued")}
        </span>
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold tabular-nums text-slate-900">
            {t("order.invoice_issued_number")} {number}
          </span>
          <button
            type="button"
            onClick={() => window.open(`/api/v1/invoices/${invoiceId}/invoice.pdf`, "_blank")}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50 min-h-touch"
          >
            {t("order.invoice_pdf")}
          </button>
        </div>
      </div>

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
            </div>
          )}
        </div>
        <div>
          <h4 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {t("order.invoice_buyer")}
          </h4>
          {invoice.buyer && <p className="mt-1 text-sm text-slate-700">{invoice.buyer.name}</p>}
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
          <dt className="text-slate-500">{t("order.invoice_vat_not_charged")}</dt>
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
