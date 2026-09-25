/**
 * Shared "customer type + buyer-company requisites" fields
 * (docs/ACCOUNTANT_REVIEW.md §4 B1): one control reused by the intake
 * create flow (CustomerStep) and the customer profile's company-details
 * edit section, so the two surfaces can never drift apart.
 *
 * VAT-registration status (Customer VAT Identity prerequisite slice) is a
 * two-choice control (Да/Не) backed by a tri-state value: unknown/
 * not-registered/registered are all valid, complete states on their own,
 * but "unknown" is only ever the pre-first-choice default — the PO does not
 * want it surfaced as a pickable third option (company-settings-fixes issue
 * 02), so it is reachable only by never having chosen Да or Не yet, never
 * by clicking anything. The VAT-number input only ever appears for the
 * registered state. This component only edits the *draft* form value — clearing a stale
 * vat_number when the effective status isn't "registered" at save time is
 * the caller's job (CustomerCompanyDetailsSection/CustomerStep), the same
 * place that already decides what to actually send on save.
 */

import { useEffect } from "react";
import { t } from "../i18n/bg";

export interface CompanyRequisitesForm {
  country: string;
  address: string;
  eik: string;
  vatRegistered: boolean | null;
  vatNumber: string;
}

// Wave 5 Issue 11: a static V1 list, no external registry — same "fixed
// choices + escape hatch" idiom Issue 23's vehicle-brand dropdown already
// established (AssetStep/serviceflow.assets.service.DEFAULT_TYPES). BG
// first/default; "Друга" reveals a free-text 2-letter code input for
// anything not listed, mirroring "Друго" there.
const COUNTRIES: { code: string; label: string }[] = [
  { code: "BG", label: "България" },
  { code: "DE", label: "Германия" },
  { code: "GR", label: "Гърция" },
  { code: "RO", label: "Румъния" },
  { code: "RS", label: "Сърбия" },
  { code: "MK", label: "Северна Македония" },
  { code: "TR", label: "Турция" },
  { code: "IT", label: "Италия" },
  { code: "FR", label: "Франция" },
  { code: "ES", label: "Испания" },
  { code: "GB", label: "Обединено кралство" },
  { code: "US", label: "САЩ" },
];
const KNOWN_COUNTRY_CODES = new Set(COUNTRIES.map((c) => c.code));

// Wave 5 Issue 11/12: mirrors backend's is_valid_eik/derive_seller_vat_number
// (business_os.shared_kernel.normalize) — a UI-only prefill convenience;
// the backend independently re-derives/validates on save regardless, so a
// mismatch here can never produce a wrong stored value.
function deriveBgVatNumber(eik: string): string | null {
  const digits = eik.trim();
  if (!/^\d+$/.test(digits)) return null;
  if (digits.length !== 9 && digits.length !== 13) return null;
  return `BG${digits}`;
}

function toggleClass(active: boolean): string {
  return `rounded-lg border px-3 py-2 text-sm font-medium min-h-touch ${
    active
      ? "border-blue-600 bg-blue-600 text-white"
      : "border-slate-300 text-slate-600 hover:bg-slate-50"
  }`;
}

export function CustomerTypeToggle({
  isCompany,
  onIsCompanyChange,
}: {
  isCompany: boolean;
  onIsCompanyChange: (isCompany: boolean) => void;
}) {
  return (
    <div className="flex gap-2" role="group" aria-label={t("customer.type_label")}>
      <button
        type="button"
        aria-pressed={!isCompany}
        onClick={() => onIsCompanyChange(false)}
        className={toggleClass(!isCompany)}
      >
        {t("customer.type_individual")}
      </button>
      <button
        type="button"
        aria-pressed={isCompany}
        onClick={() => onIsCompanyChange(true)}
        className={toggleClass(isCompany)}
      >
        {t("customer.type_company")}
      </button>
    </div>
  );
}

export function CustomerCompanyFields({
  isCompany,
  onIsCompanyChange,
  requisites,
  onRequisitesChange,
  showTypeToggle = true,
}: {
  isCompany: boolean;
  onIsCompanyChange: (isCompany: boolean) => void;
  requisites: CompanyRequisitesForm;
  onRequisitesChange: (requisites: CompanyRequisitesForm) => void;
  /** CustomerStep places the toggle above the name field instead — see
   * CustomerTypeToggle above — and renders this with `showTypeToggle={false}`
   * so the two don't render side by side. */
  showTypeToggle?: boolean;
}) {
  // Wave 5 Issue 11/12: prefill (never force) the VAT number once VAT is
  // explicitly registered and the EIK on file already structurally looks
  // like a valid BG one — only ever fills a blank field, so a value the
  // user already typed (correction or otherwise) is never overwritten.
  useEffect(() => {
    if (requisites.country !== "BG" || requisites.vatRegistered !== true) return;
    if (requisites.vatNumber.trim()) return;
    const derived = deriveBgVatNumber(requisites.eik);
    if (derived) onRequisitesChange({ ...requisites, vatNumber: derived });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requisites.country, requisites.vatRegistered, requisites.eik]);

  return (
    <div className="flex flex-col gap-3">
      {showTypeToggle && (
        <CustomerTypeToggle isCompany={isCompany} onIsCompanyChange={onIsCompanyChange} />
      )}

      {isCompany && (
        <div className="flex flex-col gap-3">
          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="customer-company-country"
            >
              {t("company.field_country")}
            </label>
            <select
              id="customer-company-country"
              value={KNOWN_COUNTRY_CODES.has(requisites.country) ? requisites.country : ""}
              onChange={(e) => onRequisitesChange({ ...requisites, country: e.target.value })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            >
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>{c.label}</option>
              ))}
              <option value="">{t("company.country_other")}</option>
            </select>
            {!KNOWN_COUNTRY_CODES.has(requisites.country) && (
              <input
                type="text"
                value={requisites.country}
                onChange={(e) => onRequisitesChange({
                  ...requisites, country: e.target.value.toUpperCase().slice(0, 2),
                })}
                placeholder={t("company.field_country")}
                maxLength={2}
                aria-label={t("company.country_other")}
                className="mt-2 w-24 rounded-lg border border-slate-300 px-3 py-2 uppercase min-h-touch"
              />
            )}
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="customer-company-address"
            >
              {t("company.field_address")}
            </label>
            <input
              id="customer-company-address"
              value={requisites.address}
              onChange={(e) => onRequisitesChange({ ...requisites, address: e.target.value })}
              maxLength={500}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
          </div>
          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="customer-company-eik"
            >
              {t("company.field_eik")}
            </label>
            <input
              id="customer-company-eik"
              value={requisites.eik}
              onChange={(e) => onRequisitesChange({ ...requisites, eik: e.target.value })}
              maxLength={20}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
          </div>

          <div>
            <span className="mb-1 block text-sm font-medium text-slate-700">
              {t("company.field_vat_registered")}
            </span>
            <div
              className="flex gap-2"
              role="group"
              aria-label={t("company.field_vat_registered")}
            >
              <button
                type="button"
                aria-pressed={requisites.vatRegistered === false}
                onClick={() => onRequisitesChange({ ...requisites, vatRegistered: false })}
                className={toggleClass(requisites.vatRegistered === false)}
              >
                {t("customer.vat_status_not_registered")}
              </button>
              <button
                type="button"
                aria-pressed={requisites.vatRegistered === true}
                onClick={() => onRequisitesChange({ ...requisites, vatRegistered: true })}
                className={toggleClass(requisites.vatRegistered === true)}
              >
                {t("customer.vat_status_registered")}
              </button>
            </div>
            {requisites.vatRegistered === null && (
              <p className="mt-1 text-sm text-amber-700">
                {t("customer.vat_status_unknown_hint")}
              </p>
            )}
          </div>

          {requisites.vatRegistered === true && (
            <div>
              <label
                className="mb-1 block text-sm font-medium text-slate-700"
                htmlFor="customer-company-vat-number"
              >
                {t("company.field_vat_number")}
              </label>
              <input
                id="customer-company-vat-number"
                value={requisites.vatNumber}
                onChange={(e) => onRequisitesChange({ ...requisites, vatNumber: e.target.value })}
                maxLength={20}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
