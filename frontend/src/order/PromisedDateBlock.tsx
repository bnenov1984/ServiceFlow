/** PromisedDateBlock (Wave 2 Issue 25): promised_on is no longer collected
 * at intake — it only becomes relevant once there's a diagnosis to promise
 * against, so it lives here on the order page, right after DiagnosisCard,
 * instead. Inline edit-in-place, same idiom as ComplaintBlock — PATCH
 * /orders/{id}, the same order-level field PATCH endpoint the intake flow's
 * removal leaves this as the only writer of. */

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { PromisedDateChips } from "../intake/PromisedDateChips";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function PromisedDateBlock({
  orderId,
  promisedOn,
  editable,
}: {
  orderId: string;
  promisedOn: string | null;
  editable: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState<string | null>(promisedOn);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const queryClient = useQueryClient();

  const save = async (next: string | null) => {
    setValue(next);
    setSaving(true);
    setError(null);
    try {
      await api.patch(`/orders/${orderId}`, { promised_on: next });
      await queryClient.invalidateQueries({ queryKey: queryKeys.order(orderId) });
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          {t("intake.promised_on")}
        </h3>
        {editable && !editing && (
          <button type="button" onClick={() => setEditing(true)} className="text-sm text-blue-700 hover:underline">
            {t("intake.change")}
          </button>
        )}
      </div>
      {editing ? (
        <div className="flex flex-col gap-2">
          <PromisedDateChips value={value} onChange={(next) => void save(next)} />
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          {!saving && (
            <button
              type="button"
              onClick={() => { setValue(promisedOn); setEditing(false); }}
              className="w-fit rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch"
            >
              {t("common.cancel")}
            </button>
          )}
        </div>
      ) : (
        <p className="text-slate-700">
          {promisedOn ?? <span className="text-slate-400">{t("order.promised_on_none")}</span>}
        </p>
      )}
    </div>
  );
}
