/**
 * Shared "customer type + buyer-company requisites" fields
 * (docs/ACCOUNTANT_REVIEW.md §4 B1): one control reused by the intake
 * create flow (CustomerStep) and the customer profile's company-details
 * edit section, so the two surfaces can never drift apart.
 *
 * VAT-registration status (Customer VAT Identity prerequisite slice) is a
 * tri-state control, not a checkbox: unknown/not-registered/registered are
 * all valid, complete states on their own — unknown must stay visually and
 * semantically distinct from "confirmed not registered," never defaulted
 * to it. The VAT-number input only ever appears for the registered state.
 * This component only edits the *draft* form value — clearing a stale
 * vat_number when the effective status isn't "registered" at save time is
 * the caller's job (CustomerCompanyDetailsSection/CustomerStep), the same
 * place that already decides what to actually send on save.
 */

import { t } from "../i18n/bg";

export interface CompanyRequisitesForm {
  address: string;
  eik: string;
  vatRegistered: boolean | null;
  vatNumber: string;
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
                aria-pressed={requisites.vatRegistered === null}
                onClick={() => onRequisitesChange({ ...requisites, vatRegistered: null })}
                className={toggleClass(requisites.vatRegistered === null)}
              >
                {t("customer.vat_status_unknown")}
              </button>
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
