/**
 * NewCustomerPage (Wave 5 Issue 14): standalone "+ Добави клиент" — customer
 * creation independent of New Order/intake. Reuses NewCustomerForm (the same
 * form intake's CustomerStep uses) rather than a second implementation. No
 * order is created here.
 */

import { useNavigate } from "react-router-dom";
import { t } from "../i18n/bg";
import { type CreatedCustomer, NewCustomerForm } from "./NewCustomerForm";

export function NewCustomerPage() {
  const navigate = useNavigate();

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-4">
      <h1 className="text-2xl font-bold text-slate-900">{t("customers.new_title")}</h1>
      <NewCustomerForm
        submitLabel={t("customers.new_create_action")}
        onCreated={(customer: CreatedCustomer) => navigate(`/customers/${customer.id}`)}
      />
    </div>
  );
}
