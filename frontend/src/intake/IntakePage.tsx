/**
 * Intake (docs/15 §6.4) — целта ≤ 2 мин. Submit sequence: order creation must
 * succeed; accessories/photos are best-effort afterwards (a failed photo upload
 * never loses the created order — partial failures surface as a toast, not a
 * blocked flow).
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../lib/api";
import { t } from "../i18n/bg";
import { useToast } from "../components/Toast";
import { AssetStep, type ResolvedAsset } from "./AssetStep";
import { CustomerStep, type ResolvedCustomer } from "./CustomerStep";
import { OrderStep, type OrderStepValue } from "./OrderStep";

interface OrderOut {
  id: string;
  number: string;
}

const DEFAULT_ORDER_VALUE: OrderStepValue = {
  complaint: "", accessories: [], photos: [], promisedOn: null,
  priority: "normal", technicianId: null,
};

function StepSection({
  number,
  title,
  active,
  children,
}: {
  number: number;
  title: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className={active ? "" : "opacity-40"}>
      <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-200 text-xs text-slate-600">
          {number}
        </span>
        {title}
      </h2>
      {children}
    </section>
  );
}

export function IntakePage() {
  const [customer, setCustomer] = useState<ResolvedCustomer | null>(null);
  const [asset, setAsset] = useState<ResolvedAsset | null>(null);
  const [orderValue, setOrderValue] = useState<OrderStepValue>(DEFAULT_ORDER_VALUE);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const navigate = useNavigate();
  const pushToast = useToast();

  const handleSubmit = async () => {
    if (!customer || !asset) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const order = await api.post<OrderOut>("/orders", {
        customer_id: customer.id,
        asset_id: asset.id,
        complaint: orderValue.complaint,
        priority: orderValue.priority,
        promised_on: orderValue.promisedOn,
        technician_id: orderValue.technicianId,
      });

      let accessoryFailures = 0;
      for (const name of orderValue.accessories) {
        try {
          await api.post(`/orders/${order.id}/accessories`, { name, qty: 1 });
        } catch {
          accessoryFailures++;
        }
      }

      let photoFailures = 0;
      for (const file of orderValue.photos) {
        const form = new FormData();
        form.append("file", file);
        form.append("stage", "reception");
        try {
          await api.post(`/orders/${order.id}/attachments`, form);
        } catch {
          photoFailures++;
        }
      }

      if (accessoryFailures > 0) {
        pushToast("error", t("intake.accessories_failed", { count: accessoryFailures }));
      }
      if (photoFailures > 0) {
        pushToast("error", t("intake.photos_failed", { count: photoFailures }));
      }

      // Same-origin navigation carries the session cookie automatically.
      window.open(`/api/v1/orders/${order.id}/protocol.pdf?type=intake`, "_blank");
      navigate(`/orders/${order.id}`);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <h1 className="text-2xl font-bold text-slate-900">{t("intake.title")}</h1>

      <StepSection number={1} title={t("intake.step_customer")} active>
        <CustomerStep
          resolved={customer}
          onResolved={(c) => { setCustomer(c); setAsset(null); }}
          onChangeRequested={() => { setCustomer(null); setAsset(null); }}
        />
      </StepSection>

      {customer && (
        <StepSection number={2} title={t("intake.step_asset")} active={!!customer}>
          <AssetStep
            customerId={customer.id}
            resolved={asset}
            onResolved={setAsset}
            onChangeRequested={() => setAsset(null)}
          />
        </StepSection>
      )}

      {customer && asset && (
        <StepSection number={3} title={t("intake.step_order")} active>
          <OrderStep
            value={orderValue}
            onChange={setOrderValue}
            onSubmit={() => void handleSubmit()}
            submitting={submitting}
            error={submitError}
          />
        </StepSection>
      )}
    </div>
  );
}
