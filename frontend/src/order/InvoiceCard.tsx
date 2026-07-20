/**
 * InvoiceCard (docs/01 §Invoice — Draft slice only): shows whether the order
 * already has a draft invoice, lets a user create one (prefilled from the
 * order's part/labor lines server-side), and edit it inline. Totals are
 * backend-authoritative (draft_total, BR-3) — this component never sums the
 * invoice total itself, only a per-line qty×price preview (not "the total").
 *
 * Issue stays disabled here too, mirroring MoneyCard's existing „Издай
 * фактура" placeholder (docs/15 grayed-nav treatment) — no fake number, no
 * client-side PDF, i18n tooltip explains it's not available yet.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useToast } from "../components/Toast";
import { Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

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

interface InvoiceDetailOut extends InvoiceOut {
  lines: InvoiceLineOut[];
  draft_total: number;
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

export function InvoiceCard({ orderId }: { orderId: string }) {
  const [open, setOpen] = useState(false);

  const { data: drafts, isLoading } = useQuery({
    queryKey: queryKeys.orderInvoiceDrafts(orderId),
    queryFn: () =>
      api.get<InvoiceOut[]>(`/invoices?order_id=${orderId}&status=draft`),
  });

  const draft = drafts?.[0] ?? null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.invoice_section_title")}
      </h3>

      {isLoading && <Skeleton className="h-6 w-32" />}

      {!isLoading && !draft && <InvoiceCreateButton orderId={orderId} onCreated={() => setOpen(true)} />}

      {!isLoading && draft && (
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
              invoiceId={draft.id}
              orderId={orderId}
              onClose={() => setOpen(false)}
            />
          )}
        </div>
      )}
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
      await queryClient.invalidateQueries({ queryKey: queryKeys.orderInvoiceDrafts(orderId) });
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
  invoiceId, orderId, onClose,
}: { invoiceId: string; orderId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const pushToast = useToast();
  const [lines, setLines] = useState<LineDraft[] | null>(null);
  const [newDescription, setNewDescription] = useState("");
  const [newQty, setNewQty] = useState("1");
  const [newPrice, setNewPrice] = useState("");
  const [newSource, setNewSource] = useState<"manual" | "adjustment">("manual");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        queryClient.invalidateQueries({ queryKey: queryKeys.orderInvoiceDrafts(orderId) }),
      ]);
      pushToast("success", t("order.invoice_saved"));
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSaving(false);
    }
  };

  if (isLoading || !invoice || lines === null) {
    return <Skeleton className="h-24" />;
  }

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
        <button
          type="button"
          disabled
          title={t("nav.coming_soon")}
          className="ml-auto cursor-not-allowed rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-300 min-h-touch"
        >
          {t("order.invoice_button")}
        </button>
      </div>
    </div>
  );
}
