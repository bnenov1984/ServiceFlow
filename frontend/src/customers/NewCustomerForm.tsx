/**
 * NewCustomerForm (Wave 5 Issue 14): the one "create a customer" form,
 * shared by intake's inline create step (CustomerStep) and the standalone
 * "+ Добави клиент" flow (NewCustomerPage) — extracted so the two never
 * drift into two independent implementations of the same validation/submit
 * logic. Individual or company, including the Wave 5 country/VAT/delivery-
 * address fields.
 *
 * order-workflow-revamp WP-B: an individual's own optional main address
 * (Q20); the delivery-address field is now checkbox-gated ("Адресът за
 * доставка е различен", Q20b) rather than always shown, and unchecked means
 * "same as the main address" (resolved server-side at read time, never
 * copied) rather than "no address". Phone (individuals, Q7) and ЕИК
 * (companies, Q8) get an inline on-blur duplicate pre-check — a UX
 * convenience only; `POST /customers` independently re-validates and is the
 * real enforcement point (service.create, `errors.customers.*_taken`).
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
}

interface DuplicateMatch {
  id: string;
  name: string;
}

export function NewCustomerForm({
  onCreated,
  onCancel,
  submitLabel,
  initialPhone = "",
  onExistingFound,
}: {
  onCreated: (customer: CreatedCustomer) => void;
  /** Intake's inline create step needs a "back to search" escape hatch;
   * the standalone page has nothing to go "back" to, so this stays optional. */
  onCancel?: () => void;
  submitLabel: string;
  initialPhone?: string;
  /** order-workflow-revamp WP-B: when a phone/ЕИК pre-check finds an
   * existing customer, CustomerStep (intake) resolves straight to it —
   * same as picking a search hit — by passing this. The standalone
   * NewCustomerPage omits it, so the form falls back to a plain link to
   * that customer's profile instead. */
  onExistingFound?: (customer: CreatedCustomer) => void;
}) {
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState(initialPhone);
  const [newEmail, setNewEmail] = useState("");
  const [isCompany, setIsCompany] = useState(false);
  const [address, setAddress] = useState("");
  const [companyRequisites, setCompanyRequisites] = useState<CompanyRequisitesForm>({
    country: "BG", address: "", eik: "", vatRegistered: null, vatNumber: "",
  });
  const [deliveryDifferent, setDeliveryDifferent] = useState(false);
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [phoneDuplicate, setPhoneDuplicate] = useState<DuplicateMatch | null>(null);
  const [eikDuplicate, setEikDuplicate] = useState<DuplicateMatch | null>(null);
  const queryClient = useQueryClient();

  const checkPhoneDuplicate = async () => {
    if (isCompany || !newPhone.trim()) {
      setPhoneDuplicate(null);
      return;
    }
    try {
      const res = await api.get<{ duplicate: DuplicateMatch | null }>(
        `/customers/phone-check?phone=${encodeURIComponent(newPhone)}`,
      );
      setPhoneDuplicate(res.duplicate);
    } catch {
      // Convenience pre-check only — a failed lookup never blocks typing;
      // POST /customers independently re-validates on submit regardless.
      setPhoneDuplicate(null);
    }
  };

  const checkEikDuplicate = async () => {
    if (!isCompany || !companyRequisites.eik.trim()) {
      setEikDuplicate(null);
      return;
    }
    try {
      const res = await api.get<{ duplicate: DuplicateMatch | null }>(
        `/customers/eik-check?eik=${encodeURIComponent(companyRequisites.eik)}`,
      );
      setEikDuplicate(res.duplicate);
    } catch {
      setEikDuplicate(null);
    }
  };

  const goToExisting = (match: DuplicateMatch, phone: string) => {
    if (onExistingFound) onExistingFound({ id: match.id, name: match.name, phone });
  };

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
        address: !isCompany ? (address.trim() || null) : null,
        delivery_address: deliveryDifferent && deliveryAddress.trim()
          ? { address: deliveryAddress.trim() } : null,
      });
      await queryClient.invalidateQueries({ queryKey: ["customers"] });
      onCreated(created);
    } catch (err) {
      if (err instanceof ApiError && err.messageKey === "errors.customers.phone_taken") {
        void checkPhoneDuplicate();
      } else if (err instanceof ApiError && err.messageKey === "errors.customers.eik_taken") {
        void checkEikDuplicate();
      }
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={createCustomer} className="flex flex-col gap-3">
      <CustomerTypeToggle
        isCompany={isCompany}
        onIsCompanyChange={(next) => { setIsCompany(next); setPhoneDuplicate(null); setEikDuplicate(null); }}
      />
      <input
        type="text"
        required
        autoFocus
        value={newName}
        onChange={(e) => setNewName(e.target.value)}
        placeholder={isCompany ? t("intake.customer_company_name") : t("intake.customer_name")}
        className="rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
      />
      <div>
        <input
          type="tel"
          required
          value={newPhone}
          onChange={(e) => { setNewPhone(e.target.value); setPhoneDuplicate(null); }}
          onBlur={() => void checkPhoneDuplicate()}
          placeholder={t("intake.customer_phone")}
          className={`w-full rounded-lg border px-3 py-2 min-h-touch ${
            phoneDuplicate ? "border-red-600" : "border-slate-300"
          }`}
        />
        {phoneDuplicate && (
          <p className="mt-1 text-sm text-red-700" role="alert">
            {t("errors.customers.phone_taken")}{" "}
            {onExistingFound ? (
              <button
                type="button"
                onClick={() => goToExisting(phoneDuplicate, newPhone)}
                className="font-medium underline"
              >
                {t("customer.pick_existing_individual")}
              </button>
            ) : (
              <a href={`/customers/${phoneDuplicate.id}`} className="font-medium underline">
                {t("customer.pick_existing_individual")}
              </a>
            )}
          </p>
        )}
      </div>
      <input
        type="email"
        value={newEmail}
        onChange={(e) => setNewEmail(e.target.value)}
        placeholder={t("intake.customer_email_optional")}
        className="rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
      />
      {!isCompany && (
        <textarea
          rows={2}
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder={t("customer.field_address")}
          maxLength={1000}
          className="rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
        />
      )}
      <CustomerCompanyFields
        isCompany={isCompany}
        onIsCompanyChange={setIsCompany}
        requisites={companyRequisites}
        onRequisitesChange={(next) => { setCompanyRequisites(next); setEikDuplicate(null); }}
        showTypeToggle={false}
        onEikBlur={() => void checkEikDuplicate()}
      />
      {isCompany && eikDuplicate && (
        <p className="text-sm text-red-700" role="alert">
          {t("errors.customers.eik_taken")}{" "}
          {onExistingFound ? (
            <button
              type="button"
              onClick={() => goToExisting(eikDuplicate, newPhone)}
              className="font-medium underline"
            >
              {t("customer.pick_existing_company")}
            </button>
          ) : (
            <a href={`/customers/${eikDuplicate.id}`} className="font-medium underline">
              {t("customer.pick_existing_company")}
            </a>
          )}
        </p>
      )}

      <div className="flex flex-col gap-2 rounded-lg border border-slate-200 p-3">
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input
            type="checkbox"
            checked={deliveryDifferent}
            onChange={(e) => setDeliveryDifferent(e.target.checked)}
          />
          {t("customer.delivery_different_checkbox")}
        </label>
        {deliveryDifferent && (
          <textarea
            rows={2}
            value={deliveryAddress}
            onChange={(e) => setDeliveryAddress(e.target.value)}
            placeholder={t("customer.field_delivery_address")}
            maxLength={500}
            className="rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
        )}
      </div>

      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting || !!phoneDuplicate || !!eikDuplicate}
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
