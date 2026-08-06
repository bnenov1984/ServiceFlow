/** Lightweight confirm (docs/15 §7) — for low-frequency, non-catastrophic
 * actions (archive, etc). Destructive-with-no-recovery actions get their own
 * dedicated dialog instead (e.g. customer anonymize, Etap 3). */

import { Dialog } from "./Dialog";
import { t } from "../i18n/bg";

export function ConfirmDialog({
  open,
  title,
  message,
  error,
  onClose,
  onConfirm,
  submitting,
}: {
  open: boolean;
  title: string;
  message: string;
  /** Rendered inside this dialog's own top-layer content, not the caller's
   * page body: a native <dialog> shown via showModal() sits above the rest
   * of the page, so an error rendered outside it is invisible while the
   * dialog stays open on failure (confirmed bug - the error existed in the
   * DOM, just behind the modal). */
  error?: string | null;
  onClose: () => void;
  onConfirm: () => void;
  submitting: boolean;
}) {
  return (
    <Dialog open={open} onClose={onClose} title={title}>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-slate-600">{message}</p>
        {error && (
          <p role="alert" className="text-sm text-red-700">{error}</p>
        )}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting}
            onClick={onConfirm}
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
