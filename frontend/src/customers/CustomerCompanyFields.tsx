/**
 * Shared "customer type + buyer-company requisites" fields
 * (docs/ACCOUNTANT_REVIEW.md §4 B1): one control reused by the intake
 * create flow (CustomerStep) and the customer profile's company-details
 * edit section, so the two surfaces can never drift apart.
 */

import { t } from "../i18n/bg";

export interface CompanyRequisitesForm {
  address: string;
  eik: string;
}

function toggleClass(active: boolean): string {
  return `rounded-lg border px-3 py-2 text-sm font-medium min-h-touch ${
    active
      ? "border-blue-600 bg-blue-600 text-white"
      : "border-slate-300 text-slate-600 hover:bg-slate-50"
  }`;
}

export function CustomerCompanyFields({
  isCompany,
  onIsCompanyChange,
  requisites,
  onRequisitesChange,
}: {
  isCompany: boolean;
  onIsCompanyChange: (isCompany: boolean) => void;
  requisites: CompanyRequisitesForm;
  onRequisitesChange: (requisites: CompanyRequisitesForm) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
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
        </div>
      )}
    </div>
  );
}
