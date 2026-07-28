import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { CompanySummary } from "./types";

function errorText(error: unknown): string {
  return error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal");
}

export function VendorCompaniesPage() {
  const companies = useQuery({
    queryKey: queryKeys.vendorCompanies,
    queryFn: () => api.get<CompanySummary[]>("/platform-admin/companies"),
  });
  const navigate = useNavigate();

  return (
    <section>
      <h1 className="mb-4 text-xl font-semibold text-slate-900">{t("vendor.companies_title")}</h1>

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
                <span className="font-medium text-slate-900">{c.name}</span>
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
