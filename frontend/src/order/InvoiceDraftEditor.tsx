/**
 * Draft Invoice line editor + Issue action (docs/01 §Invoice; Phase A —
 * docs/ACCOUNTANT_REVIEW.md 'RepairFlow Invoice V1 Freeze' §5). Shared by
 * both `InvoiceCard` (order-centric, where it can be toggled open/closed
 * inline — `onClose` provided) and `invoices/InvoiceDetailPage` (invoice-
 * centric, where it's the whole page's content and there is nothing to
 * "close" back into — `onClose` omitted) so there is exactly one draft-
 * editing implementation, not two independently maintained ones.
 *
 * `embedded` (default true) preserves `InvoiceCard`'s exact current look: a
 * top divider meant to sit below `InvoiceCard`'s own status badge/toggle
 * row. `InvoiceDetailPage` passes `embedded={false}` — it renders its own
 * page-level header above this component with nothing else inside the same
 * card, so that divider would otherwise be a seam with nothing above it.
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
import type { InvoiceDetailOut, InvoiceLineOut, InvoiceOut } from "./invoiceTypes";

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

export function InvoiceDraftEditor({
  invoiceId, orderId, deliveredAt, customerId, onClose, embedded = true,
}: {
  invoiceId: string; orderId: string; deliveredAt: string | null; customerId?: string;
  onClose?: () => void; embedded?: boolean;
}) {
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
      // Every consumer of queryKeys.invoice(invoiceId) (InvoiceCard *and*
      // InvoiceDetailPage) picks this up immediately, so a page currently
      // showing this draft flips to the issued view without a redirect.
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
          await queryClient.invalidateQueries({ queryKey: queryKeys.invoice(invoiceId) });
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
    <div className={`flex flex-col gap-3 ${embedded ? "border-t border-slate-100 pt-3" : ""}`}>
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
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch"
          >
            {t("common.close")}
          </button>
        )}
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
          customerId={customerId}
        />
      )}
    </div>
  );
}
