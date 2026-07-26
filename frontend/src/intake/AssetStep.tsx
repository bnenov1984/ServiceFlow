/**
 * Стъпка 2 АКТИВ (docs/15 §6.4): pick an existing asset of the customer, or
 * create one via a type picker → typed fields rendered from GET /asset-types'
 * field_defs. Created eagerly, same rationale as CustomerStep.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { AssetTypeIcon } from "./AssetTypeIcon";

export interface ResolvedAsset {
  id: string;
  label: string;
  assetTypeCode: string;
  duplicateWarning?: string;
}

interface FieldDef {
  key: string;
  label_bg: string;
  type: "text" | "number" | "date" | "choice";
  choices?: string[];
  identifier_kind?: string;
}

interface AssetTypeOut {
  code: string;
  name_bg: string;
  icon: string;
  field_defs: FieldDef[];
}

interface AssetHit {
  id: string;
  label: string;
  asset_type_code: string;
  archived: boolean;
}

interface AssetOut extends AssetHit {
  duplicate_asset_ids: string[];
}

// Format hints for identifier fields (docs/15 §6.4) — presentation only, the
// backend is the actual validator.
const IDENTIFIER_HINTS: Record<string, Parameters<typeof t>[0]> = {
  imei: "intake.hint_imei",
  vin: "intake.hint_vin",
  reg: "intake.hint_reg",
  serial: "intake.hint_serial",
};

// service.FieldValidationError "type" values (backend/src/serviceflow/assets/service.py)
// → per-field message key.
const FIELD_ERROR_KEYS: Record<string, Parameters<typeof t>[0]> = {
  not_a_number: "errors.assets.field_not_a_number",
  not_a_date: "errors.assets.field_not_a_date",
  invalid_choice: "errors.assets.field_invalid_choice",
  not_text: "errors.assets.field_not_text",
  unknown_field: "errors.assets.field_unknown",
};

function FieldInput({
  def,
  value,
  error,
  onChange,
}: {
  def: FieldDef;
  value: string;
  error?: string;
  onChange: (v: string) => void;
}) {
  const hintKey = def.identifier_kind ? IDENTIFIER_HINTS[def.identifier_kind] : undefined;
  const borderClass = error ? "border-red-600" : "border-slate-300";
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">{def.label_bg}</label>
      {def.type === "choice" ? (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full rounded-lg border ${borderClass} px-3 py-2 min-h-touch`}
        >
          <option value="" />
          {(def.choices ?? []).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      ) : (
        <input
          type={def.type === "number" ? "number" : def.type === "date" ? "date" : "text"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full rounded-lg border ${borderClass} px-3 py-2 min-h-touch`}
        />
      )}
      {error
        ? <p role="alert" className="mt-0.5 text-xs text-red-700">{error}</p>
        : hintKey && <p className="mt-0.5 text-xs text-slate-400">{t(hintKey)}</p>}
    </div>
  );
}

export function AssetStep({
  customerId,
  resolved,
  onResolved,
  onChangeRequested,
}: {
  customerId: string;
  resolved: ResolvedAsset | null;
  onResolved: (asset: ResolvedAsset) => void;
  onChangeRequested: () => void;
}) {
  const [mode, setMode] = useState<"pick" | "create">("pick");
  const [selectedType, setSelectedType] = useState<AssetTypeOut | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const queryClient = useQueryClient();

  const { data: types } = useQuery({
    queryKey: queryKeys.assetTypes,
    queryFn: () => api.get<AssetTypeOut[]>("/asset-types"),
  });
  const { data: existingAssets } = useQuery({
    queryKey: queryKeys.customerAssets(customerId),
    queryFn: () => api.get<AssetHit[]>(`/customers/${customerId}/assets`),
    enabled: mode === "pick",
  });

  if (resolved) {
    return (
      <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3">
        <div className="flex items-center justify-between">
          <p className="font-medium text-slate-800">{resolved.label}</p>
          <button
            type="button"
            onClick={onChangeRequested}
            className="text-sm font-medium text-blue-700 hover:underline"
          >
            {t("intake.change")}
          </button>
        </div>
        {resolved.duplicateWarning && (
          <p className="mt-2 text-sm text-amber-700" role="status">
            {resolved.duplicateWarning}
          </p>
        )}
      </div>
    );
  }

  const createAsset = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedType) return;
    setError(null);
    setFieldErrors({});
    setSubmitting(true);
    try {
      const created = await api.post<AssetOut>(`/customers/${customerId}/assets`, {
        asset_type_code: selectedType.code,
        field_values: Object.fromEntries(Object.entries(values).filter(([, v]) => v !== "")),
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.customerAssets(customerId) });
      onResolved({
        id: created.id, label: created.label, assetTypeCode: created.asset_type_code,
        duplicateWarning: created.duplicate_asset_ids.length > 0
          ? t("intake.duplicate_asset_hint") : undefined,
      });
    } catch (err) {
      if (err instanceof ApiError && err.fieldErrors.length > 0) {
        setFieldErrors(Object.fromEntries(err.fieldErrors.map((fe) => [
          Array.isArray(fe.loc) ? fe.loc.join(".") : fe.loc,
          t(FIELD_ERROR_KEYS[fe.type] ?? "errors.assets.field_unknown"),
        ])));
      }
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      {mode === "pick" ? (
        <div>
          {existingAssets && existingAssets.filter((a) => !a.archived).length > 0 && (
            <div className="mb-3 flex flex-col gap-2">
              {existingAssets.filter((a) => !a.archived).map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => onResolved({ id: a.id, label: a.label, assetTypeCode: a.asset_type_code })}
                  className="flex items-center gap-3 rounded-lg border border-slate-200 px-4 py-2 text-left hover:bg-slate-50 min-h-touch"
                >
                  <AssetTypeIcon code={a.asset_type_code} className="h-5 w-5 text-slate-400" />
                  <span className="font-medium text-slate-800">{a.label}</span>
                </button>
              ))}
            </div>
          )}
          <button
            type="button"
            onClick={() => setMode("create")}
            className="text-sm font-medium text-blue-700 hover:underline"
          >
            {t("intake.new_asset")}
          </button>
        </div>
      ) : !selectedType ? (
        <div className="grid grid-cols-4 gap-3">
          {(types ?? []).map((type) => (
            <button
              key={type.code}
              type="button"
              onClick={() => { setSelectedType(type); setValues({}); setFieldErrors({}); }}
              className="flex flex-col items-center gap-2 rounded-lg border border-slate-200 p-4 hover:border-blue-400 hover:bg-blue-50 min-h-touch"
            >
              <AssetTypeIcon code={type.code} className="h-7 w-7 text-slate-500" />
              <span className="text-sm font-medium text-slate-700">{type.name_bg}</span>
            </button>
          ))}
        </div>
      ) : (
        <form onSubmit={createAsset} className="flex flex-col gap-3">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <AssetTypeIcon code={selectedType.code} className="h-5 w-5" />
            {selectedType.name_bg}
            <button
              type="button"
              onClick={() => setSelectedType(null)}
              className="ml-auto text-blue-700 hover:underline"
            >
              {t("intake.change")}
            </button>
          </div>
          {selectedType.field_defs.map((def) => (
            <FieldInput
              key={def.key}
              def={def}
              value={values[def.key] ?? ""}
              error={fieldErrors[def.key]}
              onChange={(v) => setValues((prev) => ({ ...prev, [def.key]: v }))}
            />
          ))}
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
            >
              {t("intake.continue")}
            </button>
            <button
              type="button"
              onClick={() => setMode("pick")}
              className="rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-50 min-h-touch"
            >
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
