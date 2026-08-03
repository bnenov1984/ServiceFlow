import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { CompanySummary } from "./types";

function errorText(error: unknown): string {
  return error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal");
}

const STATUS_FILTERS: { value: string; labelKey: Parameters<typeof t>[0] }[] = [
  { value: "active", labelKey: "vendor.status_filter_active" },
  { value: "archived", labelKey: "vendor.status_filter_archived" },
  { value: "all", labelKey: "vendor.status_filter_all" },
];

export function VendorCompaniesPage() {
  const [status, setStatus] = useState("active");
  const companies = useQuery({
    queryKey: queryKeys.vendorCompaniesList(status),
    queryFn: () => api.get<CompanySummary[]>(`/platform-admin/companies?status=${status}`),
  });
  const navigate = useNavigate();

  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">{t("vendor.companies_title")}</h1>
        <button
          type="button"
          onClick={() => navigate("/vendor/companies/new")}
          className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 min-h-touch"
        >
          {t("vendor.new_company_action")}
        </button>
      </div>

      <div className="mb-4 flex items-center gap-2">
        <label className="text-sm font-medium text-slate-700" htmlFor="company-status-filter">
          {t("vendor.status_filter_label")}
        </label>
        <select
          id="company-status-filter"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm min-h-touch"
        >
          {STATUS_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>{t(f.labelKey)}</option>
          ))}
        </select>
      </div>

      {companies.isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : companies.isError ? (
        <ErrorState text={errorText(companies.error)} onRetry={() => void companies.refetch()} />
      ) : companies.data && companies.data.length > 0 ? (
        <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {companies.data.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => navigate(`/vendor/companies/${c.id}`)}
                className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-slate-50 min-h-touch"
              >
                <span className="flex items-center gap-2 font-medium text-slate-900">
                  {c.name}
                  {c.archived_at && (
                    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600">
                      {t("vendor.archived_badge")}
                    </span>
                  )}
                </span>
                <span className="flex items-center gap-4 text-sm text-slate-500">
                  <span>{c.subscription_state}</span>
                  <span>
                    {c.seat_usage}/{c.seat_limit ?? t("vendor.seat_limit_unlimited")}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState text={t("vendor.companies_empty")} />
      )}
    </section>
  );
}
