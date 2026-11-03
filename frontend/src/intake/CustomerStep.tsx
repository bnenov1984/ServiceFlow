/**
 * Стъпка 1 КЛИЕНТ (docs/15 §6.4): phone-first search → select, or inline
 * create. Customer is created eagerly on confirm (not deferred to final
 * submit), per §6.4's own requirement.
 *
 * order-workflow-revamp WP-B (Q7/Q8): a duplicate phone (individual) or ЕИК
 * (company) is now blocked at creation, not just hinted afterward — the old
 * post-create "duplicate phone" banner is gone. When NewCustomerForm's own
 * inline pre-check finds an existing match, it resolves straight to that
 * customer here, same as picking a search hit.
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { NewCustomerForm, type CreatedCustomer } from "../customers/NewCustomerForm";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export interface ResolvedCustomer {
  id: string;
  name: string;
  phone: string;
}

interface CustomerHit {
  id: string;
  name: string;
  phone: string;
  archived: boolean;
}

function useDebounced(value: string, ms: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

export function CustomerStep({
  resolved,
  onResolved,
  onChangeRequested,
}: {
  resolved: ResolvedCustomer | null;
  onResolved: (customer: ResolvedCustomer) => void;
  onChangeRequested: () => void;
}) {
  const [mode, setMode] = useState<"search" | "create">("search");
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounced(query, 300);
  const [createInitialPhone, setCreateInitialPhone] = useState("");

  const { data: hits } = useQuery({
    queryKey: queryKeys.customers(debouncedQuery),
    queryFn: () => api.get<CustomerHit[]>(`/customers?q=${encodeURIComponent(debouncedQuery)}`),
    enabled: mode === "search" && debouncedQuery.trim().length >= 2,
  });

  if (resolved) {
    return (
      <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-slate-800">{resolved.name}</p>
            <p className="text-sm text-slate-500">{resolved.phone}</p>
          </div>
          <button
            type="button"
            onClick={onChangeRequested}
            className="text-sm font-medium text-blue-700 hover:underline"
          >
            {t("intake.change")}
          </button>
        </div>
      </div>
    );
  }

  const handleCreated = (created: CreatedCustomer) => {
    onResolved({ id: created.id, name: created.name, phone: created.phone });
  };

  return (
    <div>
      {mode === "search" ? (
        <div>
          <input
            type="search"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("intake.customer_search_placeholder")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
          {debouncedQuery.trim().length >= 2 && (
            <ul className="mt-2 flex flex-col gap-1">
              {(hits ?? []).filter((h) => !h.archived).map((hit) => (
                <li key={hit.id}>
                  <button
                    type="button"
                    onClick={() => onResolved(hit)}
                    className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-4 py-2 text-left hover:bg-slate-50 min-h-touch"
                  >
                    <span className="font-medium text-slate-800">{hit.name}</span>
                    <span className="text-sm text-slate-500">{hit.phone}</span>
                  </button>
                </li>
              ))}
              {hits && hits.length === 0 && (
                <p className="px-1 py-2 text-sm text-slate-500">{t("intake.no_customer_found")}</p>
              )}
            </ul>
          )}
          <button
            type="button"
            onClick={() => {
              setMode("create");
              setCreateInitialPhone(query.match(/^\+?\d/) ? query : "");
            }}
            className="mt-3 text-sm font-medium text-blue-700 hover:underline"
          >
            {t("intake.new_customer")}
          </button>
        </div>
      ) : (
        <NewCustomerForm
          initialPhone={createInitialPhone}
          submitLabel={t("intake.continue")}
          onCreated={handleCreated}
          onExistingFound={onResolved}
          onCancel={() => setMode("search")}
        />
      )}
    </div>
  );
}
