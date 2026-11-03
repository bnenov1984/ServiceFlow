/**
 * CustomerProfilePage (docs/15 §6.7): CustomerHeader (dup warning) ·
 * AssetsSection · ActiveOrders · History (terminal) · shared ContactsList ·
 * Owner menu Анонимизирай (GDPR, two-step).
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { useToast } from "../components/Toast";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { ContactsSection } from "../order/ContactsSection";
import { AnonymizeDialog } from "./AnonymizeDialog";
import { CustomerAddressSection } from "./CustomerAddressSection";
import { CustomerAssetsSection } from "./CustomerAssetsSection";
import { CustomerCompanyDetailsSection } from "./CustomerCompanyDetailsSection";
import { CustomerDeliveryAddressSection } from "./CustomerDeliveryAddressSection";
import { CustomerOrdersSection } from "./CustomerOrdersSection";
import type { CustomerDetail } from "./types";

interface DuplicateHit {
  id: string;
  name: string;
  phone: string;
  is_company: boolean;
}

export function CustomerProfilePage() {
  const { id } = useParams<{ id: string }>();
  const customerId = id!;
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const pushToast = useToast();
  const [anonymizeOpen, setAnonymizeOpen] = useState(false);
  const [anonymizeError, setAnonymizeError] = useState<string | null>(null);
  const [anonymizeSubmitting, setAnonymizeSubmitting] = useState(false);

  const {
    data: customer, isLoading, isError, error, refetch,
  } = useQuery({
    queryKey: queryKeys.customer(customerId),
    queryFn: () => api.get<CustomerDetail>(`/customers/${customerId}`),
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });

  // order-workflow-revamp WP-B (Q4b): no duplicate-phone hint for a company
  // customer, or for an individual-vs-company clash — individual-vs-
  // individual duplicates are now blocked at creation (Q7), so this stays
  // only as a heads-up for *legacy* individual duplicates that predate that
  // rule (enforcement is forward-only, never retroactive).
  const { data: phoneMatches } = useQuery({
    queryKey: queryKeys.customers(customer?.phone ?? ""),
    queryFn: () => api.get<DuplicateHit[]>(`/customers?q=${encodeURIComponent(customer!.phone)}`),
    enabled: !!customer && !customer.anonymized && !customer.is_company,
  });
  const duplicates = customer?.is_company
    ? []
    : (phoneMatches ?? []).filter((c) => c.id !== customerId && !c.is_company);

  const runAnonymize = async () => {
    setAnonymizeSubmitting(true);
    setAnonymizeError(null);
    try {
      await api.post(`/customers/${customerId}/anonymize`);
      await queryClient.invalidateQueries({ queryKey: queryKeys.customer(customerId) });
      await queryClient.invalidateQueries({ queryKey: ["customers"] });
      pushToast("success", t("customer.anonymized_done"));
      setAnonymizeOpen(false);
    } catch (err) {
      setAnonymizeError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setAnonymizeSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-24" />
      </div>
    );
  }

  if (isError || !customer) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <EmptyState
          text={t("errors.customers.not_found")}
          action={
            <Link to="/customers" className="text-sm font-medium text-blue-700 hover:underline">
              {t("nav.customers")}
            </Link>
          }
        />
      );
    }
    return (
      <ErrorState
        text={error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal")}
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Link
        to="/customers"
        className="self-start text-sm font-medium text-blue-700 hover:underline"
      >
        {t("customer.back_to_customers")}
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
            {customer.name}
            {customer.archived && (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
                {t("customer.archived_badge")}
              </span>
            )}
          </h1>
          <p className="text-sm text-slate-500">
            <a href={`tel:${customer.phone}`} className="hover:underline">{customer.phone}</a>
            {customer.phone2 && (
              <> · <a href={`tel:${customer.phone2}`} className="hover:underline">{customer.phone2}</a></>
            )}
            {customer.email && <> · {customer.email}</>}
          </p>
          {duplicates.length > 0 && (
            <p className="mt-1 text-sm text-amber-700" role="status">
              {t("customer.duplicate_warning")}
            </p>
          )}
        </div>

        {me?.is_owner && !customer.anonymized && (
          <button
            type="button"
            onClick={() => setAnonymizeOpen(true)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 min-h-touch"
          >
            {t("customer.anonymize")}
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-4">
          <CustomerAssetsSection
            customerId={customerId}
            customerName={customer.name}
            customerPhone={customer.phone}
          />
          <CustomerOrdersSection
            customerId={customerId}
            state="open"
            title={t("customer.active_orders")}
            emptyText={t("customer.active_orders_none")}
          />
          <CustomerOrdersSection
            customerId={customerId}
            state="terminal"
            title={t("customer.history")}
            emptyText={t("customer.history_none")}
          />
        </div>
        <div className="flex flex-col gap-4">
          {customer.is_company ? (
            <CustomerCompanyDetailsSection customerId={customerId} customer={customer} />
          ) : (
            <CustomerAddressSection customerId={customerId} customer={customer} />
          )}
          <CustomerDeliveryAddressSection customerId={customerId} customer={customer} />
          <ContactsSection customerId={customerId} />
        </div>
      </div>

      <AnonymizeDialog
        open={anonymizeOpen}
        onClose={() => setAnonymizeOpen(false)}
        onConfirm={() => void runAnonymize()}
        submitting={anonymizeSubmitting}
        error={anonymizeError}
      />
    </div>
  );
}
