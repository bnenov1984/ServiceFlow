/**
 * AcceptDialog (order-workflow-revamp WP-G, Q2a/Q2b): ПРИЕМИ — the only way
 * off НОВА into Диагностика. The technician picker is pre-filled with
 * whatever intake already chose (one-click confirm, Q2b); when nothing was
 * chosen there, the Owner/worker must pick one here — the backend rejects
 * the transition without a technician either way (Q2a).
 */

import { useState } from "react";
import { TechnicianPicker } from "../../components/TechnicianPicker";
import { Dialog } from "../../components/Dialog";
import { t } from "../../i18n/bg";

export function AcceptDialog({
  open,
  currentTechnicianId,
  onClose,
  onConfirm,
  submitting,
  error,
}: {
  open: boolean;
  currentTechnicianId: string | null;
  onClose: () => void;
  onConfirm: (technicianId: string) => void;
  submitting: boolean;
  error: string | null;
}) {
  const [technicianId, setTechnicianId] = useState<string | null>(currentTechnicianId);

  return (
    <Dialog open={open} onClose={onClose} title={t("order.accept_title")}>
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
          {t("order.accept_technician_label")}
          <TechnicianPicker
            value={technicianId}
            onChange={setTechnicianId}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
        </label>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting || technicianId === null}
            onClick={() => technicianId !== null && onConfirm(technicianId)}
            className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
          >
            {submitting ? t("common.loading") : t("order.accept_confirm")}
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
