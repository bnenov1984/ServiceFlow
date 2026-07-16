/** Anonymize (GDPR, docs/15 §6.7): a dedicated two-step dialog — irreversible,
 * so it gets its own component rather than the generic ConfirmDialog. */

import { useState } from "react";
import { Dialog } from "../components/Dialog";
import { t } from "../i18n/bg";

export function AnonymizeDialog({
  open,
  onClose,
  onConfirm,
  submitting,
  error,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  submitting: boolean;
  error: string | null;
}) {
  const [step, setStep] = useState<1 | 2>(1);

  const close = () => { setStep(1); onClose(); };

  return (
    <Dialog open={open} onClose={close} title={t("customer.anonymize_title")}>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-slate-600">{t("customer.anonymize_warning")}</p>
        {step === 2 && (
          <p className="text-sm font-semibold text-red-700">
            {t("customer.anonymize_step2_warning")}
          </p>
        )}
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          {step === 1 ? (
            <button
              type="button"
              onClick={() => setStep(2)}
              className="rounded-lg bg-red-700 px-4 py-2 font-semibold text-white hover:bg-red-800 min-h-touch"
            >
              {t("customer.anonymize_step1_confirm")}
            </button>
          ) : (
            <button
              type="button"
              disabled={submitting}
              onClick={onConfirm}
              className="rounded-lg bg-red-700 px-4 py-2 font-semibold text-white hover:bg-red-800 disabled:opacity-50 min-h-touch"
            >
              {submitting ? t("common.loading") : t("customer.anonymize_step2_confirm")}
            </button>
          )}
          <button
            type="button"
            onClick={close}
            className="rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-50 min-h-touch"
          >
            {t("common.cancel")}
          </button>
        </div>
      </div>
    </Dialog>
  );
}
