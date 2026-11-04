/** OrderAdjustment (docs/15 §6.5, order-workflow-revamp WP-I, Q13, resolves
 * docs/01 OQ-5): the only way to correct an order's price — a signed amount
 * with a mandatory reason. Owner-only to add (enforced server-side too);
 * everyone sees the list, append-only (no edit/delete — a wrong one is
 * corrected by adding an offsetting entry, same discipline as a payment
 * refund). */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

interface AdjustmentOut {
  id: string;
  amount: number;
  reason: string;
  created_at: string;
}

export function AdjustmentSection({ orderId }: { orderId: string }) {
  const { me } = useAuth();
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const key = queryKeys.orderAdjustments(orderId);

  const { data: adjustments } = useQuery({
    queryKey: key,
    queryFn: () => api.get<AdjustmentOut[]>(`/orders/${orderId}/adjustments`),
  });

  const addAdjustment = async () => {
    if (!amount.trim() || !reason.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/orders/${orderId}/adjustments`, {
        amount: Number(amount), reason: reason.trim(),
      });
      setAmount("");
      setReason("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: key }),
        queryClient.invalidateQueries({ queryKey: queryKeys.order(orderId) }),
      ]);
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  if ((adjustments ?? []).length === 0 && !me?.is_owner) return null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.adjustments")}
      </h3>
      <ul className="mb-3 flex flex-col gap-1">
        {(adjustments ?? []).map((a) => (
          <li key={a.id} className="text-sm text-slate-700">
            <span className={a.amount < 0 ? "text-red-700" : "text-green-700"}>
              {a.amount > 0 ? "+" : ""}{a.amount.toFixed(2)} €
            </span>
            {" · "}{a.reason}
          </li>
        ))}
        {adjustments?.length === 0 && (
          <p className="text-sm text-slate-400">{t("order.adjustments_none")}</p>
        )}
      </ul>
      {me?.is_owner && (
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <input
              type="number" step="0.01" value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder={t("order.adjustment_amount_placeholder")}
              className="w-28 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
            />
            <input
              type="text" value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder={t("order.adjustment_reason_placeholder")}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
            />
            <button
              type="button"
              disabled={submitting}
              onClick={() => void addAdjustment()}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50 min-h-touch"
            >
              {t("intake.accessory_add")}
            </button>
          </div>
          {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
        </div>
      )}
    </div>
  );
}
