/**
 * DiagnosisCard (docs/15 §6.5, docs/01 §Diagnosis): single record, edited in
 * place (no versioning — the timeline carries history). Approval, once
 * recorded via the status-change dialogs, shows read-only here.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export interface DiagnosisValue {
  observed: string;
  cause: string;
  recommendation: string;
  estimated_cost: number | null;
  estimated_days: number | null;
  repairable: boolean | null;
  approval_required: boolean;
  approval: Record<string, unknown> | null;
}

export function DiagnosisCard({
  orderId,
  diagnosis,
  editable,
}: {
  orderId: string;
  diagnosis: DiagnosisValue | null;
  editable: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<DiagnosisValue>(
    diagnosis ?? {
      observed: "", cause: "", recommendation: "", estimated_cost: null,
      estimated_days: null, repairable: null, approval_required: false, approval: null,
    },
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const queryClient = useQueryClient();

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.put(`/orders/${orderId}/diagnosis`, {
        observed: form.observed, cause: form.cause, recommendation: form.recommendation,
        estimated_cost: form.estimated_cost, estimated_days: form.estimated_days,
        repairable: form.repairable, approval_required: form.approval_required,
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.order(orderId) });
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSaving(false);
    }
  };

  if (!editing && !diagnosis) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          {t("order.diagnosis")}
        </h3>
        {editable ? (
          <button type="button" onClick={() => setEditing(true)} className="text-sm text-blue-700 hover:underline">
            {t("order.diagnosis_add")}
          </button>
        ) : (
          <p className="text-sm text-slate-400">{t("order.diagnosis_none")}</p>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          {t("order.diagnosis")}
        </h3>
        {editable && !editing && (
          <button type="button" onClick={() => setEditing(true)} className="text-sm text-blue-700 hover:underline">
            {t("intake.change")}
          </button>
        )}
      </div>

      {editing ? (
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-slate-700">{t("order.diagnosis_observed")}</label>
          <textarea rows={2} value={form.observed}
                    onChange={(e) => setForm({ ...form, observed: e.target.value })}
                    className="rounded-lg border border-slate-300 px-3 py-2" />
          <label className="text-sm font-medium text-slate-700">{t("order.diagnosis_cause")}</label>
          <textarea rows={2} value={form.cause}
                    onChange={(e) => setForm({ ...form, cause: e.target.value })}
                    className="rounded-lg border border-slate-300 px-3 py-2" />
          <label className="text-sm font-medium text-slate-700">{t("order.diagnosis_recommendation")}</label>
          <textarea rows={2} value={form.recommendation}
                    onChange={(e) => setForm({ ...form, recommendation: e.target.value })}
                    className="rounded-lg border border-slate-300 px-3 py-2" />
          <div className="flex gap-3">
            <div>
              <label className="text-sm font-medium text-slate-700">{t("order.diagnosis_cost")}</label>
              <input type="number" min={0} step="0.01"
                     value={form.estimated_cost ?? ""}
                     onChange={(e) => setForm({ ...form, estimated_cost: e.target.value ? Number(e.target.value) : null })}
                     className="w-28 rounded-lg border border-slate-300 px-3 py-2 min-h-touch" />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t("order.diagnosis_days")}</label>
              <input type="number" min={0}
                     value={form.estimated_days ?? ""}
                     onChange={(e) => setForm({ ...form, estimated_days: e.target.value ? Number(e.target.value) : null })}
                     className="w-24 rounded-lg border border-slate-300 px-3 py-2 min-h-touch" />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.approval_required}
                   onChange={(e) => setForm({ ...form, approval_required: e.target.checked })}
                   className="h-5 w-5" />
            {t("order.diagnosis_approval_required")}
          </label>
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <div className="flex gap-2">
            <button type="button" disabled={saving} onClick={() => void save()}
                    className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch">
              {t("common.save")}
            </button>
            <button type="button" onClick={() => setEditing(false)}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch">
              {t("common.cancel")}
            </button>
          </div>
        </div>
      ) : (
        diagnosis && (
          <div className="flex flex-col gap-1 text-sm text-slate-700">
            {diagnosis.observed && <p><b>{t("order.diagnosis_observed")}:</b> {diagnosis.observed}</p>}
            {diagnosis.cause && <p><b>{t("order.diagnosis_cause")}:</b> {diagnosis.cause}</p>}
            {diagnosis.recommendation && <p><b>{t("order.diagnosis_recommendation")}:</b> {diagnosis.recommendation}</p>}
            {diagnosis.estimated_cost !== null && (
              <p><b>{t("order.diagnosis_cost")}:</b> {diagnosis.estimated_cost.toFixed(2)} €</p>
            )}
            {diagnosis.approval && (
              <p className="mt-1 rounded bg-green-50 px-2 py-1 text-green-800">
                {t("order.diagnosis_approved_note")}
              </p>
            )}
          </div>
        )
      )}
    </div>
  );
}
