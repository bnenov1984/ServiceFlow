/** Company Legal Requisites (invoice-readiness prerequisite slice,
 * docs/ACCOUNTANT_REVIEW.md §4 R1/§2 T1): Owner-only. `address`, `phone`,
 * `eik`, and `vat_registered` are editable here - МОЛ/IBAN are
 * LAW-CONFIRMED not required (R3/R4), and no separate VAT-number field
 * exists since it's always "BG" + eik once `vat_registered` is true (R2).
 * `address`/`phone` already feed the intake protocol PDF
 * (service_orders/router.py); all four will feed the invoice seller
 * snapshot once Invoice Issue exists. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, Skeleton } from "../components/States";
import { useToast } from "../components/Toast";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { SettingsNav } from "./SettingsNav";

interface CompanyRequisites {
  name: string;
  address: string | null;
  phone: string | null;
  eik: string | null;
  vat_registered: boolean;
}

interface WarrantyDefaults {
  labor_days: number | null;
  parts_days: number | null;
  // Audit correction (issue 04, 2026-09-25): free-text terms, seeded by
  // Vendor/Admin at onboarding, editable here afterward.
  standard_term: string | null;
  conditions: string | null;
  text: string | null;
  additional_conditions: string | null;
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal");
}

// "" (empty input) <-> null (no default configured); any other digit string
// <-> that integer, including "0" (explicitly "Без гаранция") — same
// empty-string-means-null convention CompletionDialog's own warranty-days
// input already uses.
function daysToInput(days: number | null | undefined): string {
  return typeof days === "number" ? String(days) : "";
}

function inputToDays(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

/** Wave 4 Issue 38: Owner-editable warranty defaults, reusing the same
 * Company settings screen (no new nav entry, no new route) — a second,
 * independently-saved card below Requisites. */
function WarrantyDefaultsSection() {
  const queryClient = useQueryClient();
  const pushToast = useToast();

  const defaults = useQuery({
    queryKey: queryKeys.companyWarrantyDefaults,
    queryFn: () => api.get<WarrantyDefaults>("/company/warranty-defaults"),
  });

  const [laborDays, setLaborDays] = useState("");
  const [partsDays, setPartsDays] = useState("");
  const [standardTerm, setStandardTerm] = useState("");
  const [conditions, setConditions] = useState("");
  const [termsText, setTermsText] = useState("");
  const [additionalConditions, setAdditionalConditions] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (defaults.data) {
      setLaborDays(daysToInput(defaults.data.labor_days));
      setPartsDays(daysToInput(defaults.data.parts_days));
      setStandardTerm(defaults.data.standard_term ?? "");
      setConditions(defaults.data.conditions ?? "");
      setTermsText(defaults.data.text ?? "");
      setAdditionalConditions(defaults.data.additional_conditions ?? "");
    }
  }, [defaults.data]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.patch<WarrantyDefaults>("/company/warranty-defaults", {
        labor_days: inputToDays(laborDays), parts_days: inputToDays(partsDays),
        standard_term: standardTerm.trim() || null,
        conditions: conditions.trim() || null,
        text: termsText.trim() || null,
        additional_conditions: additionalConditions.trim() || null,
      });
      queryClient.setQueryData(queryKeys.companyWarrantyDefaults, updated);
      pushToast("success", t("company.warranty_saved"));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  if (defaults.isLoading) return <Skeleton className="h-40 w-full max-w-lg" />;
  if (defaults.isError) {
    return <ErrorState text={errorText(defaults.error)} onRetry={() => void defaults.refetch()} />;
  }

  return (
    <form
      onSubmit={(e) => void onSubmit(e)}
      className="flex max-w-lg flex-col gap-4 rounded-lg border border-slate-200 bg-white p-6"
    >
      <div>
        <h2 className="text-lg font-semibold text-slate-900">{t("company.warranty_title")}</h2>
        <p className="text-sm text-slate-600">{t("company.warranty_hint")}</p>
      </div>

      <div>
        <label
          className="mb-1 block text-sm font-medium text-slate-700"
          htmlFor="company-labor-warranty-days"
        >
          {t("company.field_labor_warranty_days")}
        </label>
        <input
          id="company-labor-warranty-days"
          type="number"
          min={0}
          value={laborDays}
          onChange={(e) => setLaborDays(e.target.value)}
          className="w-32 rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
        />
      </div>

      <div>
        <label
          className="mb-1 block text-sm font-medium text-slate-700"
          htmlFor="company-parts-warranty-days"
        >
          {t("company.field_parts_warranty_days")}
        </label>
        <input
          id="company-parts-warranty-days"
          type="number"
          min={0}
          value={partsDays}
          onChange={(e) => setPartsDays(e.target.value)}
          className="w-32 rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
        />
      </div>

      <div>
        <label
          className="mb-1 block text-sm font-medium text-slate-700"
          htmlFor="company-warranty-standard-term"
        >
          {t("company.field_warranty_standard_term")}
        </label>
        <input
          id="company-warranty-standard-term"
          type="text"
          maxLength={200}
          value={standardTerm}
          onChange={(e) => setStandardTerm(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
        />
      </div>

      <div>
        <label
          className="mb-1 block text-sm font-medium text-slate-700"
          htmlFor="company-warranty-conditions"
        >
          {t("company.field_warranty_conditions")}
        </label>
        <textarea
          id="company-warranty-conditions"
          rows={3}
          maxLength={2000}
          value={conditions}
          onChange={(e) => setConditions(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2"
        />
      </div>

      <div>
        <label
          className="mb-1 block text-sm font-medium text-slate-700"
          htmlFor="company-warranty-text"
        >
          {t("company.field_warranty_text")}
        </label>
        <textarea
          id="company-warranty-text"
          rows={5}
          maxLength={4000}
          value={termsText}
          onChange={(e) => setTermsText(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2"
        />
      </div>

      <div>
        <label
          className="mb-1 block text-sm font-medium text-slate-700"
          htmlFor="company-warranty-additional-conditions"
        >
          {t("company.field_warranty_additional_conditions")}
        </label>
        <textarea
          id="company-warranty-additional-conditions"
          rows={3}
          maxLength={2000}
          value={additionalConditions}
          onChange={(e) => setAdditionalConditions(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2"
        />
      </div>

      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

      <button
        type="submit"
        disabled={saving}
        className="rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
      >
        {saving ? t("common.loading") : t("company.warranty_save_action")}
      </button>
    </form>
  );
}

export function CompanyRequisitesPage() {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const pushToast = useToast();

  const requisites = useQuery({
    queryKey: queryKeys.companyRequisites,
    queryFn: () => api.get<CompanyRequisites>("/company/requisites"),
    enabled: Boolean(me?.is_owner),
  });

  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [eik, setEik] = useState("");
  const [vatRegistered, setVatRegistered] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (requisites.data) {
      setName(requisites.data.name);
      setAddress(requisites.data.address ?? "");
      setPhone(requisites.data.phone ?? "");
      setEik(requisites.data.eik ?? "");
      setVatRegistered(requisites.data.vat_registered);
    }
  }, [requisites.data]);

  if (!me?.is_owner) {
    return (
      <section>
        <SettingsNav />
        <ErrorState text={t("employees.access_denied")} />
      </section>
    );
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.patch<CompanyRequisites>("/company/requisites", {
        name: name.trim(), address: address.trim(), phone: phone.trim(), eik: eik.trim(),
        vat_registered: vatRegistered,
      });
      queryClient.setQueryData(queryKeys.companyRequisites, updated);
      pushToast("success", t("company.saved"));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section>
      <SettingsNav />
      <h1 className="mb-1 text-xl font-semibold text-slate-900">
        {t("company.requisites_title")}
      </h1>
      <p className="mb-4 text-sm text-slate-600">{t("company.requisites_hint")}</p>

      {requisites.isLoading ? (
        <Skeleton className="h-48 w-full max-w-lg" />
      ) : requisites.isError ? (
        <ErrorState text={errorText(requisites.error)} onRetry={() => void requisites.refetch()} />
      ) : (
        <form
          onSubmit={(e) => void onSubmit(e)}
          className="flex max-w-lg flex-col gap-4 rounded-lg border border-slate-200 bg-white p-6"
        >
          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="company-name"
            >
              {t("company.field_name")}
            </label>
            <input
              id="company-name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={200}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="company-address"
            >
              {t("company.field_address")}
            </label>
            <input
              id="company-address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              maxLength={500}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="company-phone"
            >
              {t("company.field_phone")}
            </label>
            <input
              id="company-phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              maxLength={30}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="company-eik"
            >
              {t("company.field_eik")}
            </label>
            <input
              id="company-eik"
              value={eik}
              onChange={(e) => setEik(e.target.value)}
              maxLength={20}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
          </div>

          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <input
              type="checkbox"
              checked={vatRegistered}
              onChange={(e) => setVatRegistered(e.target.checked)}
              className="h-5 w-5"
            />
            {t("company.field_vat_registered")}
          </label>

          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
          >
            {saving ? t("common.loading") : t("company.save_action")}
          </button>
        </form>
      )}

      <div className="mt-4">
        <WarrantyDefaultsSection />
      </div>
    </section>
  );
}
