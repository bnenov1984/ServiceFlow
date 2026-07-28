/** Company Provisioning UI (business-os/18 §7 screen 3, ADR-BOS-009): the
 * first Vendor Console mutation, built directly on the existing
 * `POST /platform-admin/companies` contract — no new backend fields, no
 * seat-limit/subscription-state controls (not part of that contract; see
 * this slice's plan for why), no module metadata beyond the one module that
 * has any real enforcement anywhere in the app today. */

import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { ProvisionCompanyRequest, ProvisionCompanyResult } from "./types";

const BUSINESS_PROFILES: { code: string; labelKey: Parameters<typeof t>[0] }[] = [
  { code: "generic_repair", labelKey: "vendor.business_profile_generic_repair" },
  { code: "automotive_repair", labelKey: "vendor.business_profile_automotive_repair" },
  { code: "phone_repair", labelKey: "vendor.business_profile_phone_repair" },
  { code: "electronics_repair", labelKey: "vendor.business_profile_electronics_repair" },
  { code: "appliance_repair", labelKey: "vendor.business_profile_appliance_repair" },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 12;

function fieldKeyFromLoc(loc: string[] | string): string {
  const parts = Array.isArray(loc) ? loc : [loc];
  return (parts[0] === "body" ? parts.slice(1) : parts).join(".");
}

export function VendorNewCompanyPage() {
  const [companyName, setCompanyName] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [ownerPassword, setOwnerPassword] = useState("");
  const [businessProfile, setBusinessProfile] = useState("generic_repair");
  const [professionalServicesEnabled, setProfessionalServicesEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const validate = (): Record<string, string> => {
    const errors: Record<string, string> = {};
    if (companyName.trim().length === 0) errors.company_name = t("errors.validation");
    if (ownerName.trim().length === 0) errors.owner_name = t("errors.validation");
    if (!EMAIL_RE.test(ownerEmail)) errors.owner_email = t("errors.validation");
    if (ownerPassword.length < MIN_PASSWORD_LENGTH) errors.owner_password = t("errors.validation");
    return errors;
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting) return;

    const clientErrors = validate();
    if (Object.keys(clientErrors).length > 0) {
      setFieldErrors(clientErrors);
      return;
    }

    setError(null);
    setFieldErrors({});
    setSubmitting(true);
    try {
      const body: ProvisionCompanyRequest = {
        company_name: companyName,
        owner_name: ownerName,
        owner_email: ownerEmail,
        owner_password: ownerPassword,
        business_profile: businessProfile,
        modules: professionalServicesEnabled ? ["professional-services"] : [],
      };
      const result = await api.post<ProvisionCompanyResult>("/platform-admin/companies", body);
      await queryClient.invalidateQueries({ queryKey: queryKeys.vendorCompanies });
      navigate(`/vendor/companies/${result.company_id}`, { replace: true });
    } catch (err) {
      // Never preserve a freshly-typed, not-yet-memorized credential after a
      // failed attempt to create a brand new account.
      setOwnerPassword("");
      if (err instanceof ApiError && err.fieldErrors.length > 0) {
        setFieldErrors(Object.fromEntries(
          err.fieldErrors.map((fe) => [fieldKeyFromLoc(fe.loc), t("errors.validation")]),
        ));
      }
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
      setSubmitting(false);
    }
  };

  return (
    <section>
      <h1 className="mb-4 text-xl font-semibold text-slate-900">{t("vendor.new_company_title")}</h1>
      <form
        onSubmit={(e) => void onSubmit(e)}
        className="flex max-w-lg flex-col gap-4 rounded-lg border border-slate-200 bg-white p-6"
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="company-name">
            {t("vendor.field_company_name")}
          </label>
          <input
            id="company-name"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            className={`w-full rounded-lg border px-3 py-2 min-h-touch ${
              fieldErrors.company_name ? "border-red-600" : "border-slate-300"
            }`}
          />
          {fieldErrors.company_name && (
            <p role="alert" className="mt-0.5 text-xs text-red-700">{fieldErrors.company_name}</p>
          )}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="owner-name">
            {t("vendor.field_owner_name")}
          </label>
          <input
            id="owner-name"
            value={ownerName}
            onChange={(e) => setOwnerName(e.target.value)}
            className={`w-full rounded-lg border px-3 py-2 min-h-touch ${
              fieldErrors.owner_name ? "border-red-600" : "border-slate-300"
            }`}
          />
          {fieldErrors.owner_name && (
            <p role="alert" className="mt-0.5 text-xs text-red-700">{fieldErrors.owner_name}</p>
          )}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="owner-email">
            {t("auth.email")}
          </label>
          <input
            id="owner-email"
            type="email"
            value={ownerEmail}
            onChange={(e) => setOwnerEmail(e.target.value)}
            className={`w-full rounded-lg border px-3 py-2 min-h-touch ${
              fieldErrors.owner_email ? "border-red-600" : "border-slate-300"
            }`}
          />
          {fieldErrors.owner_email && (
            <p role="alert" className="mt-0.5 text-xs text-red-700">{fieldErrors.owner_email}</p>
          )}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="owner-password">
            {t("auth.password")}
          </label>
          <input
            id="owner-password"
            type="password"
            value={ownerPassword}
            onChange={(e) => setOwnerPassword(e.target.value)}
            className={`w-full rounded-lg border px-3 py-2 min-h-touch ${
              fieldErrors.owner_password ? "border-red-600" : "border-slate-300"
            }`}
          />
          {fieldErrors.owner_password ? (
            <p role="alert" className="mt-0.5 text-xs text-red-700">{fieldErrors.owner_password}</p>
          ) : (
            <p className="mt-0.5 text-xs text-slate-400">{t("vendor.field_owner_password_hint")}</p>
          )}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="business-profile">
            {t("vendor.field_business_profile")}
          </label>
          <select
            id="business-profile"
            value={businessProfile}
            onChange={(e) => setBusinessProfile(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          >
            {BUSINESS_PROFILES.map((p) => (
              <option key={p.code} value={p.code}>{t(p.labelKey)}</option>
            ))}
          </select>
        </div>

        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input
            type="checkbox"
            checked={professionalServicesEnabled}
            onChange={(e) => setProfessionalServicesEnabled(e.target.checked)}
          />
          {t("app.propertyflow")}
        </label>

        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
        >
          {submitting ? t("common.loading") : t("vendor.new_company_submit")}
        </button>
      </form>
    </section>
  );
}
