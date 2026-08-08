/**
 * Customer company (buyer) legal details — edit-in-place, DiagnosisCard's
 * idiom (view / "Промени" → edit form / Save-Cancel). Scoped to
 * is_company/company_requisites only, not a general customer editor
 * (docs/ACCOUNTANT_REVIEW.md §4 B1).
 */

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { CustomerCompanyFields } from "./CustomerCompanyFields";
import type { CustomerDetail } from "./types";

function requisitesFrom(customer: CustomerDetail) {
  return {
    address: customer.company_requisites?.address ?? "",
    eik: customer.company_requisites?.eik ?? "",
  };
}

export function CustomerCompanyDetailsSection({
  customerId,
  customer,
}: {
  customerId: string;
  customer: CustomerDetail;
}) {
  const [editing, setEditing] = useState(false);
  const [isCompany, setIsCompany] = useState(customer.is_company);
  const [requisites, setRequisites] = useState(requisitesFrom(customer));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const queryClient = useQueryClient();

  const startEditing = () => {
    setIsCompany(customer.is_company);
    setRequisites(requisitesFrom(customer));
    setError(null);
    setEditing(true);
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.patch(`/customers/${customerId}`, {
        is_company: isCompany,
        // Toggling to individual never erases previously-stored requisites
        // here — preservation over destructive mutation, since nothing in
        // the domain rules requires clearing them on a temporary toggle.
        company_requisites: isCompany
          ? { address: requisites.address.trim() || null, eik: requisites.eik.trim() || null }
          : customer.company_requisites,
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.customer(customerId) });
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
          {t("customer.company_details")}
        </h3>
        {!editing && (
          <button
            type="button"
            onClick={startEditing}
            className="text-sm text-blue-700 hover:underline"
          >
            {t("intake.change")}
          </button>
        )}
      </div>

      {editing ? (
        <div className="flex flex-col gap-3">
          <CustomerCompanyFields
            isCompany={isCompany}
            onIsCompanyChange={setIsCompany}
            requisites={requisites}
            onRequisitesChange={setRequisites}
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
              onClick={() => setEditing(false)}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch"
            >
              {t("common.cancel")}
            </button>
          </div>
        </div>
      ) : customer.is_company ? (
        <dl className="flex flex-col gap-2 text-sm text-slate-700">
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
              {t("company.field_address")}
            </dt>
            <dd className="mt-0.5">{customer.company_requisites?.address || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
              {t("company.field_eik")}
            </dt>
            <dd className="mt-0.5">{customer.company_requisites?.eik || "—"}</dd>
          </div>
        </dl>
      ) : (
        <p className="text-sm text-slate-400">{t("customer.company_details_none")}</p>
      )}
    </div>
  );
}
