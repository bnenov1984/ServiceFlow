/**
 * NewInvoicePage (Wave 6 Issue 30 — manual invoice creation): lets a user
 * create an invoice directly from the central /invoices workspace without
 * first creating a ServiceOrder. Reuses the exact same customer search
 * (invoices/InvoicesPage's `CustomerFilter`) and standalone customer-
 * creation form (customers/NewCustomerForm, Wave 5 Issue 14) rather than
 * building a second customer picker/form — this page's own job is only:
 * resolve a customer_id, POST /invoices, then hand off to the normal
 * invoice detail route (/invoices/{id}), where the existing
 * InvoiceDraftEditor/Issue flow takes over completely unchanged. No
 * ServiceOrder is ever created by this flow.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type CreatedCustomer, NewCustomerForm } from "../customers/NewCustomerForm";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import type { InvoiceOut } from "../order/invoiceTypes";
import { CustomerFilter } from "./InvoicesPage";

export function NewInvoicePage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"search" | "create">("search");
  const [selected, setSelected] = useState<{ id: string; name: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createDraft = async (customerId: string) => {
    setSubmitting(true);
    setError(null);
    try {
      const invoice = await api.post<InvoiceOut>("/invoices", { customer_id: customerId });
      navigate(`/invoices/${invoice.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-4">
      <h1 className="text-2xl font-bold text-slate-900">{t("invoices.new_title")}</h1>

      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

      {mode === "search" ? (
        <div className="flex flex-col gap-3">
          <label className="text-sm font-medium text-slate-700">
            {t("invoices.new_customer_label")}
          </label>
          <CustomerFilter
            selected={selected}
            onSelect={setSelected}
            onClear={() => setSelected(null)}
          />
          <button
            type="button"
            onClick={() => setMode("create")}
            className="self-start text-sm text-blue-700 hover:underline"
          >
            {t("invoices.new_customer_create_action")}
          </button>
          <button
            type="button"
            disabled={!selected || submitting}
            onClick={() => selected && void createDraft(selected.id)}
            className="self-start rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
          >
            {submitting ? t("common.loading") : t("invoices.new_continue")}
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <button
            type="button"
            onClick={() => setMode("search")}
            className="self-start text-sm text-blue-700 hover:underline"
          >
            {t("invoices.new_customer_back_to_search")}
          </button>
          <NewCustomerForm
            submitLabel={t("invoices.new_continue")}
            onCreated={(customer: CreatedCustomer) => void createDraft(customer.id)}
          />
        </div>
      )}
    </div>
  );
}
