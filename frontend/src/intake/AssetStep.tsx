/**
 * Стъпка 2 АКТИВ (docs/15 §6.4): pick an existing asset of the customer, or
 * create one via a type picker → typed fields rendered from GET /asset-types'
 * field_defs. Created eagerly, same rationale as CustomerStep.
 *
 * Cleanup batch Issue 20 (VIN-first): for a vehicle, VIN is looked up
 * *before* the full field form is shown — `draft.vinCheckDone` gates
 * between the VIN-only sub-form and the full form. Reuses the exact same
 * `GET /assets/by-vin` lookup and reuse/transfer-owner actions the
 * submit-time check already used (see `lookupVinConflict`/
 * `useExistingVehicle`/`transferOwner` below) — no second VIN identity
 * implementation, no weakened uniqueness: the submit-time check inside
 * `createAsset` still runs too, as a safety net if the VIN field is edited
 * again after the upfront check passes.
 *
 * Cleanup batch Issue 22: all in-progress, unsaved draft state (mode,
 * selected type, typed field values, the VIN-first phase, an open owner
 * conflict) is lifted to the parent (`draft`/`onDraftChange`, the same
 * controlled-component shape `OrderStep` already uses for its own value) so
 * it survives this component unmounting/remounting when the user goes back
 * to the Customer step and forward again — no global state, just the
 * existing lifted-state pattern applied one level further up.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
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

// Issue 20: tenant-wide VIN lookup response (GET /assets/by-vin) — includes
// the current owner so the intake choice dialog can name them without a
// second round trip.
interface AssetByVinOut {
  id: string;
  label: string;
  asset_type_code: string;
  customer_id: string;
  customer_name: string;
}

// The full in-progress Asset-step draft, lifted to IntakePage (Issue 22) so
// it survives a Customer-step round trip. `values` covers every field of
// whichever type is selected, including the vehicle "vin" key — the same
// record backs both the VIN-first sub-form and the full field form, so a
// VIN typed in the first is already present (retained) in the second.
export interface AssetStepDraft {
  mode: "pick" | "create";
  selectedTypeCode: string | null;
  values: Record<string, string>;
  // Issue 20: only meaningful when selectedTypeCode === "vehicle" — false
  // means "show the VIN-only sub-form first", true means "VIN has been
  // checked (or explicitly skipped) — show the full field form."  Ignored
  // for every non-vehicle type (they never show the VIN-first sub-form).
  vinCheckDone: boolean;
  ownerConflict: AssetByVinOut | null;
}

export const DEFAULT_ASSET_STEP_DRAFT: AssetStepDraft = {
  mode: "pick", selectedTypeCode: null, values: {}, vinCheckDone: false, ownerConflict: null,
};

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

// Form state (and FieldInput's controlled <input>) keeps every field as a
// string regardless of def.type — the DOM only ever gives back strings from
// onChange. At the form/schema boundary (submission), a "number" field must
// become a real JSON number, or the backend's validate_field_values()
// (isinstance(raw, int | float)) rejects a perfectly valid "2015"/"100000"
// as errors.assets.field_not_a_number. Only coerces when the result is a
// real number — an unparseable value (should not occur through a native
// <input type="number">, but must still fail closed rather than silently
// becoming `null`/JSON `NaN`→null, which would skip backend validation
// entirely) is left as the original string, so the backend's own check
// still rejects it as not_a_number instead of treating it as absent.
export function coerceFieldValue(def: FieldDef | undefined, value: string): unknown {
  if (def?.type !== "number") return value;
  const n = Number(value);
  return Number.isNaN(n) ? value : n;
}

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
  draft,
  onDraftChange,
}: {
  customerId: string;
  resolved: ResolvedAsset | null;
  onResolved: (asset: ResolvedAsset) => void;
  onChangeRequested: () => void;
  draft: AssetStepDraft;
  onDraftChange: (next: AssetStepDraft) => void;
}) {
  const { mode, selectedTypeCode, values, vinCheckDone, ownerConflict } = draft;
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const queryClient = useQueryClient();

  const patchDraft = (patch: Partial<AssetStepDraft>) => onDraftChange({ ...draft, ...patch });

  // The draft resets to its defaults once an asset is actually
  // resolved (picked, reused, transferred, or freshly created) — the
  // in-progress-data-survives-navigation guarantee is about *unsaved* work,
  // not about carrying a finished attempt's leftovers into the next one.
  const resolve = (asset: ResolvedAsset) => {
    onDraftChange(DEFAULT_ASSET_STEP_DRAFT);
    onResolved(asset);
  };

  const { data: types } = useQuery({
    queryKey: queryKeys.assetTypes,
    queryFn: () => api.get<AssetTypeOut[]>("/asset-types"),
  });
  const { data: existingAssets } = useQuery({
    queryKey: queryKeys.customerAssets(customerId),
    queryFn: () => api.get<AssetHit[]>(`/customers/${customerId}/assets`),
    enabled: mode === "pick",
  });

  const selectedType = types?.find((t2) => t2.code === selectedTypeCode) ?? null;
  const isVehicle = selectedType?.code === "vehicle";
  const vinDef = selectedType?.field_defs.find((d) => d.identifier_kind === "vin");
  const showVinFirst = isVehicle && !vinCheckDone && !ownerConflict;

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

  // Issue 20: VIN must be looked up tenant-wide *before* a vehicle is
  // created, never after. Returns null when there's nothing to check (not a
  // vehicle, or no VIN field def, or a blank VIN) or no match was found
  // (404) — either way the caller should just proceed with the normal
  // create.
  const lookupVinConflict = async (): Promise<AssetByVinOut | null> => {
    if (selectedType?.code !== "vehicle") return null;
    const vin = vinDef ? values[vinDef.key]?.trim() : "";
    if (!vin) return null;
    try {
      return await api.get<AssetByVinOut>(`/assets/by-vin?vin=${encodeURIComponent(vin)}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }
  };

  // Issue 20's upfront check: "Провери VIN" on the VIN-first sub-form.
  const checkVin = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const match = await lookupVinConflict();
      if (match) {
        if (match.customer_id === customerId) {
          // Already this customer's own vehicle — reuse it outright, same
          // as picking it from the "pick existing" list would have done.
          resolve({ id: match.id, label: match.label, assetTypeCode: match.asset_type_code });
        } else {
          patchDraft({ ownerConflict: match });
        }
      } else {
        patchDraft({ vinCheckDone: true });
      }
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  // Issue 20's explicit escape hatch: a vehicle asset doesn't strictly
  // require a VIN (the domain treats it as just another optional field), so
  // a blank VIN must have its own path forward rather than silently forcing
  // the user through a lookup that has nothing to check.
  const continueWithoutVin = () => patchDraft({ vinCheckDone: true });

  const createAsset = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedType) return;
    setError(null);
    setFieldErrors({});
    setSubmitting(true);
    try {
      // Safety net (Wave 3 original behavior, unchanged): the VIN field can
      // still be edited inside the full form after the Issue 20 upfront
      // check passed, so this re-checks at submit time too — never weakens
      // the existing company-scoped normalized VIN uniqueness.
      const match = await lookupVinConflict();
      if (match) {
        if (match.customer_id === customerId) {
          resolve({ id: match.id, label: match.label, assetTypeCode: match.asset_type_code });
        } else {
          patchDraft({ ownerConflict: match });
        }
        return;
      }

      const fieldDefsByKey = new Map(selectedType.field_defs.map((def) => [def.key, def]));
      const created = await api.post<AssetOut>(`/customers/${customerId}/assets`, {
        asset_type_code: selectedType.code,
        field_values: Object.fromEntries(
          Object.entries(values)
            .filter(([, v]) => v !== "")
            .map(([k, v]) => [k, coerceFieldValue(fieldDefsByKey.get(k), v)]),
        ),
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.customerAssets(customerId) });
      resolve({
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

  // "Използвай автомобила" — MUST NOT change Asset.customer_id or ownership
  // history; the new order simply uses this intake's customer together with
  // the existing vehicle's asset_id (docs/business-os Wave 3, Issue 20).
  const useExistingVehicle = () => {
    if (!ownerConflict) return;
    resolve({
      id: ownerConflict.id, label: ownerConflict.label,
      assetTypeCode: ownerConflict.asset_type_code,
    });
  };

  // "Смени собственик" — the only explicit action that reassigns ownership.
  const transferOwner = async () => {
    if (!ownerConflict) return;
    setSubmitting(true);
    setError(null);
    try {
      const asset = await api.post<AssetOut>(`/assets/${ownerConflict.id}/transfer-owner`, {
        customer_id: customerId,
      });
      resolve({ id: asset.id, label: asset.label, assetTypeCode: asset.asset_type_code });
    } catch (err) {
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
                  onClick={() => resolve({ id: a.id, label: a.label, assetTypeCode: a.asset_type_code })}
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
            onClick={() => patchDraft({ mode: "create" })}
            className="text-sm font-medium text-blue-700 hover:underline"
          >
            {t("intake.new_asset")}
          </button>
        </div>
      ) : !selectedType ? (
        <div>
          <div className="grid grid-cols-4 gap-3">
            {(types ?? []).map((type) => (
              <button
                key={type.code}
                type="button"
                onClick={() => {
                  patchDraft({
                    selectedTypeCode: type.code, values: {}, vinCheckDone: false, ownerConflict: null,
                  });
                  setFieldErrors({});
                }}
                className="flex flex-col items-center gap-2 rounded-lg border border-slate-200 p-4 hover:border-blue-400 hover:bg-blue-50 min-h-touch"
              >
                <AssetTypeIcon code={type.code} className="h-7 w-7 text-slate-500" />
                <span className="text-sm font-medium text-slate-700">{type.name_bg}</span>
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => patchDraft({ mode: "pick" })}
            className="mt-3 rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-50 min-h-touch"
          >
            {t("common.cancel")}
          </button>
        </div>
      ) : ownerConflict ? (
        <div className="flex flex-col gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <p className="text-sm text-slate-800">
            {t("intake.vin_owner_conflict", { owner: ownerConflict.customer_name })}
          </p>
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={useExistingVehicle}
              disabled={submitting}
              className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
            >
              {t("intake.use_existing_vehicle")}
            </button>
            <button
              type="button"
              onClick={() => void transferOwner()}
              disabled={submitting}
              className="rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-50 disabled:opacity-50 min-h-touch"
            >
              {t("intake.transfer_owner")}
            </button>
          </div>
        </div>
      ) : showVinFirst && vinDef ? (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <AssetTypeIcon code={selectedType.code} className="h-5 w-5" />
            {selectedType.name_bg}
            <button
              type="button"
              onClick={() => patchDraft({ selectedTypeCode: null, vinCheckDone: false, ownerConflict: null })}
              className="ml-auto text-blue-700 hover:underline"
            >
              {t("intake.change")}
            </button>
          </div>
          <p className="text-sm text-slate-500">{t("intake.vin_first_hint")}</p>
          <FieldInput
            def={vinDef}
            value={values[vinDef.key] ?? ""}
            onChange={(v) => patchDraft({ values: { ...values, [vinDef.key]: v } })}
          />
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void checkVin()}
              disabled={submitting}
              className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
            >
              {submitting ? t("common.loading") : t("intake.vin_check")}
            </button>
            <button
              type="button"
              onClick={continueWithoutVin}
              disabled={submitting}
              className="rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-50 disabled:opacity-50 min-h-touch"
            >
              {t("intake.vin_continue_without")}
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={createAsset} className="flex flex-col gap-3">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <AssetTypeIcon code={selectedType.code} className="h-5 w-5" />
            {selectedType.name_bg}
            <button
              type="button"
              onClick={() => patchDraft({ selectedTypeCode: null, vinCheckDone: false, ownerConflict: null })}
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
              onChange={(v) => patchDraft({ values: { ...values, [def.key]: v } })}
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
              onClick={() => patchDraft({ mode: "pick" })}
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
