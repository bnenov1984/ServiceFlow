/**
 * Invoice Annulment confirmation (Wave 6 Issue 30, docs/ACCOUNTANT_REVIEW.md
 * §7 case A — ЗДДС чл. 116): a dedicated dialog, same reasoning as
 * `InvoiceIssueDialog`/`AnonymizeDialog` — irreversible, so it gets an
 * explicit confirm step with a mandatory reason field, not an immediate
 * action on button click. The warning copy is deliberately scoped to
 * "this was a mistake" (case A) — a real supply reduction/return needs a
 * credit note (postponed), never this action.
 */

import { useEffect, useState } from "react";
import { Dialog } from "../components/Dialog";
import { t } from "../i18n/bg";

export function AnnulInvoiceDialog({
  open,
  onClose,
  onConfirm,
  submitting,
  error,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  submitting: boolean;
  error: string | null;
}) {
  const [reason, setReason] = useState("");

  // Re-seed only on a fresh open, so an in-progress edit isn't silently
  // overwritten if the dialog stays open after a failed attempt.
  useEffect(() => {
    if (open) setReason("");
  }, [open]);

  const trimmedReason = reason.trim();

  return (
    <Dialog open={open} onClose={onClose} title={t("order.invoice_annul_title")}>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-slate-600">{t("order.invoice_annul_warning")}</p>
        <p className="text-sm font-semibold text-red-700">
          {t("order.invoice_annul_irreversible")}
        </p>

        <div>
          <label
            className="mb-1 block text-sm font-medium text-slate-700"
            htmlFor="invoice-annul-reason"
          >
            {t("order.invoice_annul_reason_label")}
          </label>
          <textarea
            id="invoice-annul-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </div>

        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting || !trimmedReason}
            onClick={() => onConfirm(trimmedReason)}
            className="rounded-lg bg-red-700 px-4 py-2 font-semibold text-white hover:bg-red-800 disabled:opacity-50 min-h-touch"
          >
            {submitting ? t("common.loading") : t("order.invoice_annul_confirm")}
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
