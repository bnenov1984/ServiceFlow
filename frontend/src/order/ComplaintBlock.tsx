/** ComplaintBlock (docs/15 §6.5): inline edit, locked once the order is terminal. */

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function ComplaintBlock({
  orderId,
  complaint,
  editable,
}: {
  orderId: string;
  complaint: string;
  editable: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(complaint);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const queryClient = useQueryClient();

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.patch(`/orders/${orderId}`, { complaint: value });
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
          {t("order.complaint")}
        </h3>
        {editable && !editing && (
          <button type="button" onClick={() => setEditing(true)} className="text-sm text-blue-700 hover:underline">
            {t("intake.change")}
          </button>
        )}
      </div>
      {editing ? (
        <div className="flex flex-col gap-2">
          <textarea
            autoFocus
            rows={3}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2"
          />
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              disabled={saving}
              onClick={() => void save()}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
            >
              {t("common.save")}
            </button>
            <button
              type="button"
              onClick={() => { setValue(complaint); setEditing(false); }}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch"
            >
              {t("common.cancel")}
            </button>
          </div>
        </div>
      ) : (
        <p className="whitespace-pre-wrap text-slate-700">{complaint}</p>
      )}
    </div>
  );
}
