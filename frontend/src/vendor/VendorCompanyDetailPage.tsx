import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { CompanyDetail, EntitlementResult } from "./types";

// The only module with any real enforcement anywhere in the app today
// (professional_services.deps.require_ps_active) — no module-metadata
// endpoint exists, so this is the same "smallest canonical mapping" literal
// already used in VendorNewCompanyPage.tsx, not a new shared constant.
const PROFESSIONAL_SERVICES = "professional-services";

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
  const queryClient = useQueryClient();
  const company = useQuery({
    queryKey: queryKeys.vendorCompany(id ?? ""),
    queryFn: () => api.get<CompanyDetail>(`/platform-admin/companies/${id}`),
    enabled: Boolean(id),
  });

  const [entitlementSubmitting, setEntitlementSubmitting] = useState(false);
  const [entitlementError, setEntitlementError] = useState<string | null>(null);
  const [confirmRevokeOpen, setConfirmRevokeOpen] = useState(false);

  const isNotFound = company.isError && company.error instanceof ApiError
    && company.error.status === 404;

  const applyEntitlementResult = (result: EntitlementResult) => {
    queryClient.setQueryData(queryKeys.vendorCompany(id ?? ""), (old: CompanyDetail | undefined) =>
      old ? { ...old, active_modules: result.active_modules } : old);
    void queryClient.invalidateQueries({ queryKey: queryKeys.vendorCompanies });
  };

  const toggleEntitlement = async (method: "grant" | "revoke") => {
    if (entitlementSubmitting || !id) return;
    setEntitlementSubmitting(true);
    setEntitlementError(null);
    const path = `/platform-admin/companies/${id}/modules/${PROFESSIONAL_SERVICES}`;
    try {
      const result = method === "grant"
        ? await api.put<EntitlementResult>(path)
        : await api.delete<EntitlementResult>(path);
      applyEntitlementResult(result);
      setConfirmRevokeOpen(false);
    } catch (err) {
      setEntitlementError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setEntitlementSubmitting(false);
    }
  };

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
            {company.data.trial_ends_at && (
              <Field label={t("vendor.field_trial_ends_at")} value={company.data.trial_ends_at} />
            )}
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

          <div className="mt-4 flex flex-col items-start gap-2">
            {company.data.active_modules.includes(PROFESSIONAL_SERVICES) ? (
              <button
                type="button"
                disabled={entitlementSubmitting}
                onClick={() => setConfirmRevokeOpen(true)}
                className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 min-h-touch"
              >
                {t("vendor.revoke_professional_services")}
              </button>
            ) : (
              <button
                type="button"
                disabled={entitlementSubmitting}
                onClick={() => void toggleEntitlement("grant")}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 min-h-touch"
              >
                {t("vendor.grant_professional_services")}
              </button>
            )}
            {entitlementError && (
              <p role="alert" className="text-sm text-red-700">{entitlementError}</p>
            )}
          </div>

          <ConfirmDialog
            open={confirmRevokeOpen}
            title={t("vendor.revoke_module_title")}
            message={t("vendor.revoke_module_confirm")}
            onClose={() => setConfirmRevokeOpen(false)}
            onConfirm={() => void toggleEntitlement("revoke")}
            submitting={entitlementSubmitting}
          />
        </>
      ) : null}
    </section>
  );
}
