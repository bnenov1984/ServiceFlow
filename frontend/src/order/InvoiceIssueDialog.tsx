/**
 * Invoice Issue confirmation (Phase A, docs/ACCOUNTANT_REVIEW.md 'RepairFlow
 * Invoice V1 Freeze' §5): issuing assigns a final legal number and freezes
 * the document, so it gets an explicit confirm step, not an immediate action
 * on button click — same reasoning as AnonymizeDialog, one dedicated
 * component rather than the generic ConfirmDialog (this one needs an editable
 * date field, not just a message).
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { t } from "../i18n/bg";

export interface IssueErrorInfo {
  message: string;
  key: string;
}

export function InvoiceIssueDialog({
  open,
  onClose,
  onConfirm,
  submitting,
  error,
  draftTotal,
  defaultTaxEventDate,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (taxEventDate: string) => void;
  submitting: boolean;
  error: IssueErrorInfo | null;
  draftTotal: number;
  defaultTaxEventDate: string;
}) {
  const [taxEventDate, setTaxEventDate] = useState(defaultTaxEventDate);

  // Re-seed only on a fresh open, so an in-progress edit (including through
  // an error + retry cycle, since the dialog stays open on failure) is never
  // silently overwritten while it's still open.
  useEffect(() => {
    if (open) setTaxEventDate(defaultTaxEventDate);
  }, [open, defaultTaxEventDate]);

  return (
    <Dialog open={open} onClose={onClose} title={t("order.invoice_issue_title")}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">{t("order.invoice_total")}</span>
          <span className="font-semibold tabular-nums text-slate-900">
            {draftTotal.toFixed(2)} €
          </span>
        </div>

        <div>
          <label
            className="mb-1 block text-sm font-medium text-slate-700"
            htmlFor="invoice-issue-tax-event-date"
          >
            {t("order.invoice_issue_tax_event_date")}
          </label>
          <input
            id="invoice-issue-tax-event-date"
            type="date"
            value={taxEventDate}
            onChange={(e) => setTaxEventDate(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
        </div>

        <p className="text-sm text-slate-600">{t("order.invoice_issue_warning")}</p>

        {error && (
          <div role="alert" className="flex flex-col gap-1 text-sm text-red-700">
            <p>{error.message}</p>
            {error.key === "errors.invoices.seller_incomplete" && (
              <Link to="/settings/company" className="font-medium underline">
                {t("order.invoice_issue_settings_link")}
              </Link>
            )}
          </div>
        )}

        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting || !taxEventDate}
            onClick={() => onConfirm(taxEventDate)}
            className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
          >
            {submitting ? t("common.loading") : t("order.invoice_button")}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-50 min-h-touch"
          >
            {t("common.cancel")}
          </button>
        </div>
      </div>
    </Dialog>
  );
}
