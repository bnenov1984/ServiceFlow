/**
 * ReasonDialog (docs/15 §6.6): terminal outcomes (Отказана/Неремонтируема/
 * Анулирана) and BR-2 unlock. Reason required where the backend rules say so
 * (cancelled/declined/unlock); optional otherwise — the field is always shown
 * so nothing is silently skipped either way.
 */

import { useState } from "react";
import { Dialog } from "../../components/Dialog";
import { t } from "../../i18n/bg";

export function ReasonDialog({
  open,
  title,
  fieldLabel,
  requireReason,
  onClose,
  onConfirm,
  submitting,
  error,
}: {
  open: boolean;
  title: string;
  fieldLabel?: string;
  requireReason: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  submitting: boolean;
  error: string | null;
}) {
  const [reason, setReason] = useState("");

  return (
    <Dialog open={open} onClose={onClose} title={title}>
      <div className="flex flex-col gap-3">
        <label className="text-sm font-medium text-slate-700">
          {fieldLabel ?? t("order.reason_label")}
        </label>
        <textarea
          autoFocus
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2"
        />
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting || (requireReason && reason.trim().length === 0)}
            onClick={() => onConfirm(reason.trim())}
            className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
          >
            {submitting ? t("common.loading") : t("order.confirm")}
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
