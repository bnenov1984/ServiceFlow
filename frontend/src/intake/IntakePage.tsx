/**
 * Intake (docs/15 §6.4) — целта ≤ 2 мин. Submit sequence: order creation must
 * succeed; accessories/photos are best-effort afterwards (a failed photo upload
 * never loses the created order — partial failures surface as a toast, not a
 * blocked flow).
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError, api } from "../lib/api";
import { apiUrl } from "../lib/apiUrl";
import { t } from "../i18n/bg";
import { useToast } from "../components/Toast";
import { invalidateOrderViews } from "../lib/orderQueries";
import { queryKeys } from "../lib/queryKeys";
import { AssetStep, DEFAULT_ASSET_STEP_DRAFT, type AssetStepDraft, type ResolvedAsset } from "./AssetStep";
import { CustomerStep, type ResolvedCustomer } from "./CustomerStep";
import { OrderStep, type OrderStepValue } from "./OrderStep";

/** docs/15 §6.7 "Нова поръчка за този актив" — the customer profile navigates
 * here with router state instead of a route param, since intake stays a
 * single route regardless of where it's entered from. */
interface IntakeLocationState {
  preselectedCustomer?: ResolvedCustomer;
  preselectedAsset?: ResolvedAsset;
}

interface OrderOut {
  id: string;
  number: string;
}

interface CustomerDetailOut {
  is_company: boolean;
  // order-workflow-revamp WP-B (Q20b): the main address, used as the
  // courier-prefill fallback when delivery_address is null.
  address: string | null;
  company_requisites: { address: string | null } | null;
  delivery_address: { address: string } | null;
}

const DEFAULT_ORDER_VALUE: OrderStepValue = {
  complaint: "", accessories: [], photos: [], partLines: [],
  priority: "normal", technicianId: null, mileage: "",
  deliveryMethod: "pickup", deliveryAddress: "",
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
  const location = useLocation();
  const preselected = (location.state ?? {}) as IntakeLocationState;
  const [customer, setCustomer] = useState<ResolvedCustomer | null>(
    preselected.preselectedCustomer ?? null,
  );
  const [asset, setAsset] = useState<ResolvedAsset | null>(preselected.preselectedAsset ?? null);
  // Cleanup batch Issue 22: lifted here (not local to AssetStep) so a round
  // trip back to the Customer step and forward again doesn't lose whatever
  // the user had already typed into the Asset step — same lifted-state
  // shape orderValue below already uses for OrderStep.
  const [assetStepDraft, setAssetStepDraft] = useState<AssetStepDraft>(DEFAULT_ASSET_STEP_DRAFT);
  const [orderValue, setOrderValue] = useState<OrderStepValue>(DEFAULT_ORDER_VALUE);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const navigate = useNavigate();
  const pushToast = useToast();
  const queryClient = useQueryClient();

  // Wave 5 Issue 12: the resolved customer's own default delivery address,
  // for OrderStep's courier-address prefill — a plain read, unrelated to
  // whether the customer was just created or picked from search.
  const { data: customerDetail } = useQuery({
    queryKey: queryKeys.customer(customer?.id ?? ""),
    queryFn: () => api.get<CustomerDetailOut>(`/customers/${customer!.id}`),
    enabled: !!customer,
  });

  const handleSubmit = async () => {
    if (!customer || !asset) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const mileage = orderValue.mileage.trim() ? Number(orderValue.mileage) : null;
      const order = await api.post<OrderOut>("/orders", {
        customer_id: customer.id,
        asset_id: asset.id,
        complaint: orderValue.complaint,
        priority: orderValue.priority,
        technician_id: orderValue.technicianId,
        mileage: mileage !== null && !Number.isNaN(mileage) ? mileage : null,
        delivery_method: orderValue.deliveryMethod,
        delivery_address: orderValue.deliveryMethod === "courier" && orderValue.deliveryAddress.trim()
          ? { address: orderValue.deliveryAddress.trim() } : null,
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

      // Issue 29: parts already known at intake, same best-effort pattern —
      // a failed part line never loses the created order.
      let partFailures = 0;
      for (const line of orderValue.partLines) {
        try {
          await api.post(`/orders/${order.id}/part-lines`, {
            name: line.name, unit_price: line.unitPrice,
          });
        } catch {
          partFailures++;
        }
      }

      if (accessoryFailures > 0) {
        pushToast("error", t("intake.accessories_failed", { count: accessoryFailures }));
      }
      if (photoFailures > 0) {
        pushToast("error", t("intake.photos_failed", { count: photoFailures }));
      }
      if (partFailures > 0) {
        pushToast("error", t("intake.parts_failed", { count: partFailures }));
      }

      void invalidateOrderViews(queryClient, order.id);

      // Same-origin navigation carries the session cookie automatically.
      window.open(apiUrl(`/api/v1/orders/${order.id}/protocol.pdf?type=intake`), "_blank");
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
            draft={assetStepDraft}
            onDraftChange={setAssetStepDraft}
          />
        </StepSection>
      )}

      {customer && asset && (
        <StepSection number={3} title={t("intake.step_order")} active>
          <OrderStep
            value={orderValue}
            assetTypeCode={asset.assetTypeCode}
            defaultDeliveryAddress={
              customerDetail?.delivery_address?.address
              ?? (customerDetail?.is_company
                  ? customerDetail?.company_requisites?.address
                  : customerDetail?.address)
              ?? null
            }
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
