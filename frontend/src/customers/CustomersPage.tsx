/**
 * CustomersPage (docs/15 §6.7): SearchInput (name/phone, server-normalized) +
 * CustomerRow (name, phones tel:, active-order count from the list response).
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { CustomerListItem } from "./types";

function useDebounced(value: string, ms: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

function CustomerRow({ customer }: { customer: CustomerListItem }) {
  return (
    <li className="border-b border-slate-100 last:border-0">
      <Link
        to={`/customers/${customer.id}`}
        className="flex items-center justify-between gap-3 px-3 py-3 hover:bg-slate-50 min-h-touch"
      >
        <div>
          <p className="font-medium text-slate-900">{customer.name}</p>
          <p className="text-sm text-slate-500">
            <a
              href={`tel:${customer.phone}`}
              onClick={(e) => e.stopPropagation()}
              className="hover:underline"
            >
              {customer.phone}
            </a>
          </p>
        </div>
        {customer.active_orders_count > 0 && (
          <span className="whitespace-nowrap rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
            {t("customers.active_orders_count", { count: customer.active_orders_count })}
          </span>
        )}
      </Link>
    </li>
  );
}

export function CustomersPage() {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounced(query, 300);

  const {
    data: customers, isLoading, isError, error, refetch,
  } = useQuery({
    queryKey: queryKeys.customers(debouncedQuery),
    queryFn: () => api.get<CustomerListItem[]>(`/customers?q=${encodeURIComponent(debouncedQuery)}`),
  });

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold text-slate-900">{t("nav.customers")}</h1>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t("customers.search_placeholder")}
        className="mb-4 w-full max-w-md rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
      />

      {isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState
          text={error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal")}
          onRetry={() => void refetch()}
        />
      ) : customers && customers.length > 0 ? (
        <ul className="rounded-lg border border-slate-200 bg-white">
          {customers.map((c) => <CustomerRow key={c.id} customer={c} />)}
        </ul>
      ) : (
        <EmptyState text={t("customers.empty")} />
      )}
    </div>
  );
}
