import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { CompanyDetail } from "./types";

function errorText(error: unknown): string {
  return error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal");
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="text-slate-900">{value}</dd>
    </div>
  );
}

export function VendorCompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const company = useQuery({
    queryKey: queryKeys.vendorCompany(id ?? ""),
    queryFn: () => api.get<CompanyDetail>(`/platform-admin/companies/${id}`),
    enabled: Boolean(id),
  });

  const isNotFound = company.isError && company.error instanceof ApiError
    && company.error.status === 404;

  return (
    <section>
      <Link to="/vendor/companies" className="mb-4 inline-block text-sm text-blue-700 hover:underline">
        {t("vendor.back_to_companies")}
      </Link>

      {company.isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      ) : isNotFound ? (
        <ErrorState text={t("vendor.company_not_found")} />
      ) : company.isError ? (
        <ErrorState text={errorText(company.error)} onRetry={() => void company.refetch()} />
      ) : company.data ? (
        <>
          <h1 className="mb-4 text-xl font-semibold text-slate-900">{company.data.name}</h1>
          <dl className="grid grid-cols-1 gap-4 rounded-lg border border-slate-200 bg-white p-6 sm:grid-cols-2">
            <Field label={t("vendor.field_business_profile")} value={company.data.business_profile} />
            <Field
              label={t("vendor.field_active_modules")}
              value={company.data.active_modules.length > 0
                ? company.data.active_modules.join(", ")
                : t("vendor.no_active_modules")}
            />
            <Field label={t("vendor.field_subscription_state")} value={company.data.subscription_state} />
            <Field
              label={t("vendor.field_seat_usage")}
              value={`${company.data.seat_usage}/${company.data.seat_limit ?? t("vendor.seat_limit_unlimited")}`}
            />
            <Field label={t("vendor.field_created_at")} value={company.data.created_at} />
            <Field
              label={t("vendor.field_subscription_changed_at")}
              value={company.data.subscription_state_changed_at}
            />
          </dl>
        </>
      ) : null}
    </section>
  );
}
