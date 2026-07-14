/**
 * ApprovalDialog (docs/15 §6.6, BR-7): leaving Чака клиент forward requires a
 * recorded approval — channel + amount. Rejection routes to ReasonDialog
 * instead (a different transition target, handled by the parent).
 */

import { useState } from "react";
import { Dialog } from "../../components/Dialog";
import { t } from "../../i18n/bg";

const CHANNELS = ["phone", "in_person", "message"] as const;
type Channel = (typeof CHANNELS)[number];

const CHANNEL_LABEL: Record<Channel, Parameters<typeof t>[0]> = {
  phone: "order.channel_phone",
  in_person: "order.channel_in_person",
  message: "order.channel_message",
};

export function ApprovalDialog({
  open,
  onClose,
  onConfirm,
  submitting,
  error,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (channel: Channel, amount: number | null) => void;
  submitting: boolean;
  error: string | null;
}) {
  const [channel, setChannel] = useState<Channel>("phone");
  const [amount, setAmount] = useState("");

  return (
    <Dialog open={open} onClose={onClose} title={t("order.approval_title")}>
      <div className="flex flex-col gap-3">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            {t("order.approval_channel")}
          </label>
          <div className="flex gap-2">
            {CHANNELS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setChannel(c)}
                aria-pressed={channel === c}
                className={`rounded-full border px-3 py-1.5 text-sm font-medium min-h-touch ${
                  channel === c
                    ? "border-blue-600 bg-blue-600 text-white"
                    : "border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {t(CHANNEL_LABEL[c])}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            {t("order.approval_amount")}
          </label>
          <input
            type="number"
            min={0}
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
        </div>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting}
            onClick={() => onConfirm(channel, amount.trim() ? Number(amount) : null)}
            className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
          >
            {submitting ? t("common.loading") : t("order.approval_confirm")}
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
