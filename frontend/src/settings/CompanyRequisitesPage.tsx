/** Company Legal Requisites (invoice-readiness prerequisite slice,
 * docs/ACCOUNTANT_REVIEW.md §4 R1/§2 T1): Owner-only. `address`, `phone`,
 * `eik`, and `vat_registered` are editable here - МОЛ/IBAN are
 * LAW-CONFIRMED not required (R3/R4), and no separate VAT-number field
 * exists since it's always "BG" + eik once `vat_registered` is true (R2).
 * `address`/`phone` already feed the intake protocol PDF
 * (service_orders/router.py); all four will feed the invoice seller
 * snapshot once Invoice Issue exists. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, Skeleton } from "../components/States";
import { useToast } from "../components/Toast";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { SettingsNav } from "./SettingsNav";

interface CompanyRequisites {
  address: string | null;
  phone: string | null;
  eik: string | null;
  vat_registered: boolean;
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal");
}

export function CompanyRequisitesPage() {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const pushToast = useToast();

  const requisites = useQuery({
    queryKey: queryKeys.companyRequisites,
    queryFn: () => api.get<CompanyRequisites>("/company/requisites"),
    enabled: Boolean(me?.is_owner),
  });

  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [eik, setEik] = useState("");
  const [vatRegistered, setVatRegistered] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (requisites.data) {
      setAddress(requisites.data.address ?? "");
      setPhone(requisites.data.phone ?? "");
      setEik(requisites.data.eik ?? "");
      setVatRegistered(requisites.data.vat_registered);
    }
  }, [requisites.data]);

  if (!me?.is_owner) {
    return (
      <section>
        <SettingsNav />
        <ErrorState text={t("employees.access_denied")} />
      </section>
    );
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.patch<CompanyRequisites>("/company/requisites", {
        address: address.trim(), phone: phone.trim(), eik: eik.trim(),
        vat_registered: vatRegistered,
      });
      queryClient.setQueryData(queryKeys.companyRequisites, updated);
      pushToast("success", t("company.saved"));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section>
      <SettingsNav />
      <h1 className="mb-1 text-xl font-semibold text-slate-900">
        {t("company.requisites_title")}
      </h1>
      <p className="mb-4 text-sm text-slate-600">{t("company.requisites_hint")}</p>

      {requisites.isLoading ? (
        <Skeleton className="h-48 w-full max-w-lg" />
      ) : requisites.isError ? (
        <ErrorState text={errorText(requisites.error)} onRetry={() => void requisites.refetch()} />
      ) : (
        <form
          onSubmit={(e) => void onSubmit(e)}
          className="flex max-w-lg flex-col gap-4 rounded-lg border border-slate-200 bg-white p-6"
        >
          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="company-address"
            >
              {t("company.field_address")}
            </label>
            <input
              id="company-address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              maxLength={500}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="company-phone"
            >
              {t("company.field_phone")}
            </label>
            <input
              id="company-phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              maxLength={30}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="company-eik"
            >
              {t("company.field_eik")}
            </label>
            <input
              id="company-eik"
              value={eik}
              onChange={(e) => setEik(e.target.value)}
              maxLength={20}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
          </div>

          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <input
              type="checkbox"
              checked={vatRegistered}
              onChange={(e) => setVatRegistered(e.target.checked)}
              className="h-5 w-5"
            />
            {t("company.field_vat_registered")}
          </label>

          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
          >
            {saving ? t("common.loading") : t("company.save_action")}
          </button>
        </form>
      )}
    </section>
  );
}
