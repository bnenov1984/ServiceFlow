/**
 * Стъпка 1 КЛИЕНТ (docs/15 §6.4): phone-first search → select, or inline
 * create with a non-blocking duplicate hint. Customer is created eagerly on
 * confirm (not deferred to final submit) so the duplicate hint from the
 * create response can surface immediately, per §6.4's own requirement.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { CustomerCompanyFields } from "../customers/CustomerCompanyFields";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export interface ResolvedCustomer {
  id: string;
  name: string;
  phone: string;
  duplicateWarning?: string;
}

interface CustomerHit {
  id: string;
  name: string;
  phone: string;
  archived: boolean;
}

interface CustomerOut extends CustomerHit {
  duplicate_ids: string[];
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
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [isCompany, setIsCompany] = useState(false);
  const [companyRequisites, setCompanyRequisites] = useState({ address: "", eik: "" });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const queryClient = useQueryClient();

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
        {resolved.duplicateWarning && (
          <p className="mt-2 text-sm text-amber-700" role="status">
            {resolved.duplicateWarning}
          </p>
        )}
      </div>
    );
  }

  const createCustomer = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const created = await api.post<CustomerOut>("/customers", {
        name: newName, phone: newPhone, email: newEmail || null,
        is_company: isCompany,
        company_requisites: isCompany
          ? { address: companyRequisites.address.trim() || null, eik: companyRequisites.eik.trim() || null }
          : null,
      });
      await queryClient.invalidateQueries({ queryKey: ["customers"] });
      onResolved({
        id: created.id, name: created.name, phone: created.phone,
        duplicateWarning: created.duplicate_ids.length > 0
          ? t("intake.duplicate_phone_hint") : undefined,
      });
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
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
            onClick={() => { setMode("create"); setNewPhone(query.match(/^\+?\d/) ? query : ""); }}
            className="mt-3 text-sm font-medium text-blue-700 hover:underline"
          >
            {t("intake.new_customer")}
          </button>
        </div>
      ) : (
        <form onSubmit={createCustomer} className="flex flex-col gap-3">
          <input
            type="text"
            required
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder={t("intake.customer_name")}
            className="rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
          <input
            type="tel"
            required
            value={newPhone}
            onChange={(e) => setNewPhone(e.target.value)}
            placeholder={t("intake.customer_phone")}
            className="rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
          <input
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder={t("intake.customer_email_optional")}
            className="rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
          <CustomerCompanyFields
            isCompany={isCompany}
            onIsCompanyChange={setIsCompany}
            requisites={companyRequisites}
            onRequisitesChange={setCompanyRequisites}
          />
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
            >
              {t("intake.continue")}
            </button>
            <button
              type="button"
              onClick={() => setMode("search")}
              className="rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-50 min-h-touch"
            >
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
