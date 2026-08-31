/**
 * NewCustomerForm (Wave 5 Issue 14): the one "create a customer" form,
 * shared by intake's inline create step (CustomerStep) and the standalone
 * "+ Добави клиент" flow (NewCustomerPage) — extracted so the two never
 * drift into two independent implementations of the same validation/submit
 * logic. Individual or company, including the Wave 5 country/VAT/delivery-
 * address fields.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import {
  CustomerCompanyFields,
  CustomerTypeToggle,
  type CompanyRequisitesForm,
} from "./CustomerCompanyFields";

export interface CreatedCustomer {
  id: string;
  name: string;
  phone: string;
  duplicate_ids: string[];
}

export function NewCustomerForm({
  onCreated,
  onCancel,
  submitLabel,
  initialPhone = "",
}: {
  onCreated: (customer: CreatedCustomer) => void;
  /** Intake's inline create step needs a "back to search" escape hatch;
   * the standalone page has nothing to go "back" to, so this stays optional. */
  onCancel?: () => void;
  submitLabel: string;
  initialPhone?: string;
}) {
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState(initialPhone);
  const [newEmail, setNewEmail] = useState("");
  const [isCompany, setIsCompany] = useState(false);
  const [companyRequisites, setCompanyRequisites] = useState<CompanyRequisitesForm>({
    country: "BG", address: "", eik: "", vatRegistered: null, vatNumber: "",
  });
  // Wave 5 Issue 12: unconditional — an individual customer may have a
  // default delivery address too, not just companies.
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const queryClient = useQueryClient();

  const createCustomer = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const created = await api.post<CreatedCustomer>("/customers", {
        name: newName, phone: newPhone, email: newEmail || null,
        is_company: isCompany,
        vat_registered: isCompany ? companyRequisites.vatRegistered : null,
        company_requisites: isCompany
          ? {
              country: companyRequisites.country,
              address: companyRequisites.address.trim() || null,
              eik: companyRequisites.eik.trim() || null,
              vat_number: companyRequisites.vatRegistered === true
                ? (companyRequisites.vatNumber.trim() || null) : null,
            }
          : null,
        delivery_address: deliveryAddress.trim() ? { address: deliveryAddress.trim() } : null,
      });
      await queryClient.invalidateQueries({ queryKey: ["customers"] });
      onCreated(created);
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={createCustomer} className="flex flex-col gap-3">
      <CustomerTypeToggle isCompany={isCompany} onIsCompanyChange={setIsCompany} />
      <input
        type="text"
        required
        autoFocus
        value={newName}
        onChange={(e) => setNewName(e.target.value)}
        placeholder={isCompany ? t("intake.customer_company_name") : t("intake.customer_name")}
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
        showTypeToggle={false}
      />
      <input
        type="text"
        value={deliveryAddress}
        onChange={(e) => setDeliveryAddress(e.target.value)}
        placeholder={t("intake.customer_delivery_address_optional")}
        className="rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
      />
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
        >
          {submitLabel}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-50 min-h-touch"
          >
            {t("common.cancel")}
          </button>
        )}
      </div>
    </form>
  );
}
