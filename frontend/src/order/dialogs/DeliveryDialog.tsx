/**
 * DeliveryDialog (docs/15 §6.6): Готова → Предадена. Accessories-returned
 * checklist + warranty days + optional payment (docs/01 §Payment: delivery
 * needs "плащане(ия)", not full settlement — an open balance is allowed).
 * Invoice stays Etap 4 (noted, not built).
 */

import { useState } from "react";
import { Dialog } from "../../components/Dialog";
import { t } from "../../i18n/bg";

interface AccessoryItem {
  id: string;
  name: string;
  qty: number;
  returned: boolean;
}

export interface DeliveryPaymentInput {
  amount: number;
  method: "cash" | "card" | "bank";
  note: string;
}

const PAYMENT_METHODS = ["cash", "card", "bank"] as const;

export function DeliveryDialog({
  open,
  onClose,
  onConfirm,
  accessories,
  onToggleReturned,
  submitting,
  error,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (warrantyDays: number | null, payment: DeliveryPaymentInput | null) => void;
  accessories: AccessoryItem[];
  onToggleReturned: (id: string, returned: boolean) => void;
  submitting: boolean;
  error: string | null;
}) {
  const [warrantyDays, setWarrantyDays] = useState("");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<DeliveryPaymentInput["method"]>("cash");
  const [paymentNote, setPaymentNote] = useState("");

  return (
    <Dialog open={open} onClose={onClose} title={t("order.delivery_title")}>
      <div className="flex flex-col gap-4">
        {accessories.length > 0 && (
          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">
              {t("order.delivery_accessories")}
            </p>
            <ul className="flex flex-col gap-1">
              {accessories.map((a) => (
                <li key={a.id}>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={a.returned}
                      onChange={(e) => onToggleReturned(a.id, e.target.checked)}
                      className="h-5 w-5"
                    />
                    {a.name}{a.qty > 1 ? ` ×${a.qty}` : ""}
                  </label>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            {t("order.delivery_warranty_days")}
          </label>
          <input
            type="number"
            min={0}
            value={warrantyDays}
            onChange={(e) => setWarrantyDays(e.target.value)}
            className="w-32 rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
        </div>
        <div>
          <p className="mb-2 text-sm font-medium text-slate-700">
            {t("order.delivery_payment")}
          </p>
          <div className="flex flex-col gap-2">
            <input
              type="number"
              min={0}
              step="0.01"
              placeholder={t("order.delivery_payment_amount")}
              value={paymentAmount}
              onChange={(e) => setPaymentAmount(e.target.value)}
              className="w-32 rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
            <div className="flex gap-2">
              {PAYMENT_METHODS.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setPaymentMethod(m)}
                  aria-pressed={paymentMethod === m}
                  className={`rounded-full border px-3 py-1.5 text-sm font-medium min-h-touch ${
                    paymentMethod === m
                      ? "border-blue-600 bg-blue-600 text-white"
                      : "border-slate-300 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {t(`order.payment_method_${m}`)}
                </button>
              ))}
            </div>
            <input
              type="text"
              placeholder={t("order.delivery_payment_note_placeholder")}
              value={paymentNote}
              onChange={(e) => setPaymentNote(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
          </div>
        </div>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting}
            onClick={() => onConfirm(
              warrantyDays.trim() ? Number(warrantyDays) : null,
              paymentAmount.trim()
                ? { amount: Number(paymentAmount), method: paymentMethod, note: paymentNote.trim() }
                : null,
            )}
            className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
          >
            {submitting ? t("common.loading") : t("order.delivery_confirm")}
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
