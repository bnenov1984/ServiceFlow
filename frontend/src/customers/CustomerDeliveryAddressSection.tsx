/**
 * CustomerDeliveryAddressSection (Wave 5 Issue 12; checkbox semantics from
 * order-workflow-revamp WP-B, Q20b): ONE optional default delivery address,
 * individual or company customer alike — deliberately separate from
 * CustomerCompanyDetailsSection/CustomerAddressSection (the main address).
 *
 * "Адресът за доставка е различен" unchecked means delivery resolves to the
 * main address *at read time* — `delivery_address` is stored as null, never
 * a copy of the main address, so a later edit to the main address is always
 * reflected (same read-time-fallback contract service_orders/router.py's
 * courier prefill uses at order creation).
 */

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { CustomerDetail } from "./types";

function mainAddressOf(customer: CustomerDetail): string | null {
  return customer.is_company ? customer.company_requisites?.address ?? null : customer.address;
}

export function CustomerDeliveryAddressSection({
  customerId,
  customer,
}: {
  customerId: string;
  customer: CustomerDetail;
}) {
  const [editing, setEditing] = useState(false);
  const [different, setDifferent] = useState(customer.delivery_address !== null);
  const [address, setAddress] = useState(customer.delivery_address?.address ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const queryClient = useQueryClient();
  const mainAddress = mainAddressOf(customer);

  const startEditing = () => {
    setDifferent(customer.delivery_address !== null);
    setAddress(customer.delivery_address?.address ?? "");
    setError(null);
    setEditing(true);
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.patch(`/customers/${customerId}`, {
        delivery_address: different && address.trim() ? { address: address.trim() } : null,
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.customer(customerId) });
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          {t("customer.delivery_address_title")}
        </h3>
        {!editing && (
          <button
            type="button"
            onClick={startEditing}
            className="text-sm text-blue-700 hover:underline"
          >
            {t("intake.change")}
          </button>
        )}
      </div>

      {editing ? (
        <div className="flex flex-col gap-3">
          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <input
              type="checkbox"
              checked={different}
              onChange={(e) => setDifferent(e.target.checked)}
            />
            {t("customer.delivery_different_checkbox")}
          </label>
          {different && (
            <div>
              <label
                className="mb-1 block text-sm font-medium text-slate-700"
                htmlFor="customer-delivery-address"
              >
                {t("customer.field_delivery_address")}
              </label>
              <textarea
                id="customer-delivery-address"
                rows={2}
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                maxLength={500}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
              />
            </div>
          )}
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              disabled={saving}
              onClick={() => void save()}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
            >
              {t("common.save")}
            </button>
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch"
            >
              {t("common.cancel")}
            </button>
          </div>
        </div>
      ) : customer.delivery_address ? (
        <p className="whitespace-pre-wrap text-sm text-slate-700">
          {customer.delivery_address.address}
        </p>
      ) : mainAddress ? (
        <p className="whitespace-pre-wrap text-sm text-slate-700">
          {mainAddress}{" "}
          <span className="text-xs text-slate-400">{t("customer.delivery_address_same_as_main")}</span>
        </p>
      ) : (
        <p className="text-sm text-slate-400">{t("customer.delivery_address_none")}</p>
      )}
    </div>
  );
}
