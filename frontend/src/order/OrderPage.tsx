/**
 * OrderPage (docs/15 §6.5): one screen, no tabs. Parallel fetches (order +
 * customer + asset), 404 handled explicitly, everything else composed from
 * the section components built for this screen.
 */

import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { isTerminal } from "../lib/statusMatrix";
import { AccessoriesListSection } from "./AccessoriesListSection";
import { AssetCard } from "./AssetCard";
import { ComplaintBlock } from "./ComplaintBlock";
import { ContactsSection } from "./ContactsSection";
import { CustomerCard } from "./CustomerCard";
import { DiagnosisCard, type DiagnosisValue } from "./DiagnosisCard";
import { InvoiceCard } from "./InvoiceCard";
import { LaborLinesSection } from "./LaborLinesSection";
import { MoneyCard } from "./MoneyCard";
import { OrderHeader } from "./OrderHeader";
import { PartLinesSection } from "./PartLinesSection";
import { PhotosGrid } from "./PhotosGrid";
import { PromisedDateBlock } from "./PromisedDateBlock";
import { ReadySummary } from "./ReadySummary";
import { TasksChecklist } from "./TasksChecklist";
import { TimelineSection } from "./TimelineSection";
import { VehicleHistorySection } from "./VehicleHistorySection";

interface OrderDetailOut {
  id: string;
  number: string;
  customer_id: string;
  asset_id: string;
  complaint: string;
  status_code: string;
  archived: boolean;
  promised_on: string | null;
  diagnosis: DiagnosisValue | null;
  estimated_total: number;
  paid_amount: number;
  balance: number;
  // Order-completion timestamp — the frozen client-side default source for
  // InvoiceCard's tax_event_date suggestion (docs/ACCOUNTANT_REVIEW.md D1:
  // a convenience default only, never sent unedited/unseen).
  delivered_at: string | null;
  // Wave 3 Issues 21/26/27 — mileage recorded on THIS visit, if any.
  mileage: number | null;
}

interface AssetServiceHistoryOut {
  current_mileage: number | null;
}

interface CustomerOut {
  id: string;
  name: string;
  phone: string;
}

interface AssetOut {
  id: string;
  asset_type_code: string;
  label: string;
  field_values: Record<string, unknown>;
}

export function OrderPage() {
  const { id } = useParams<{ id: string }>();
  const orderId = id!;

  const {
    data: order, isLoading, isError, error, refetch,
  } = useQuery({
    queryKey: queryKeys.order(orderId),
    queryFn: () => api.get<OrderDetailOut>(`/orders/${orderId}`),
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });

  const { data: customer } = useQuery({
    queryKey: queryKeys.customer(order?.customer_id ?? ""),
    queryFn: () => api.get<CustomerOut>(`/customers/${order!.customer_id}`),
    enabled: !!order,
  });

  const { data: asset } = useQuery({
    queryKey: ["asset", order?.asset_id ?? ""],
    queryFn: () => api.get<AssetOut>(`/assets/${order!.asset_id}`),
    enabled: !!order,
  });

  const isVehicle = asset?.asset_type_code === "vehicle";
  const { data: serviceHistory } = useQuery({
    queryKey: queryKeys.assetServiceHistory(order?.asset_id ?? ""),
    queryFn: () => api.get<AssetServiceHistoryOut>(`/assets/${order!.asset_id}/service-history`),
    enabled: !!order && isVehicle,
  });

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      </div>
    );
  }

  if (isError || !order) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <EmptyState
          text={t("errors.orders.not_found")}
          action={
            <Link to="/orders" className="text-sm font-medium text-blue-700 hover:underline">
              {t("nav.orders")}
            </Link>
          }
        />
      );
    }
    return (
      <ErrorState
        text={error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal")}
        onRetry={() => void refetch()}
      />
    );
  }

  const orderIsTerminal = order.archived || isTerminal(order.status_code);
  // Issue 8: "ready" is operationally frozen — complaint/diagnosis/parts/
  // labor render as a single read-only recap instead of their normal
  // editable sections. Corrections go back through the existing workflow
  // (move the order back to "repair" first via OrderHeader's status menu,
  // unchanged), not an edit control here. Nothing about the underlying
  // stored order/diagnosis/part/labor data changes — this is presentation
  // only, and every other section (tasks, accessories, photos, invoice,
  // timeline) keeps working exactly as it does for any other open order.
  const isReady = order.status_code === "ready";

  return (
    <div className="flex flex-col gap-4">
      <OrderHeader
        orderId={order.id}
        number={order.number}
        statusCode={order.status_code}
        archived={order.archived}
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-4">
          {customer && (
            <CustomerCard customerId={customer.id} name={customer.name} phone={customer.phone} />
          )}
          {asset && (
            <AssetCard
              assetTypeCode={asset.asset_type_code}
              label={asset.label}
              fieldValues={asset.field_values}
              currentMileage={isVehicle ? serviceHistory?.current_mileage : undefined}
            />
          )}
          {isVehicle && (
            <VehicleHistorySection assetId={order.asset_id} currentOrderId={order.id} />
          )}
          {isReady ? (
            <ReadySummary
              orderId={order.id}
              complaint={order.complaint}
              diagnosis={order.diagnosis}
              estimatedTotal={order.estimated_total}
              paidAmount={order.paid_amount}
              balance={order.balance}
            />
          ) : (
            <>
              <ComplaintBlock orderId={order.id} complaint={order.complaint} editable={!orderIsTerminal} />
              <DiagnosisCard orderId={order.id} diagnosis={order.diagnosis} editable={!orderIsTerminal} />
            </>
          )}
          <PromisedDateBlock orderId={order.id} promisedOn={order.promised_on} editable={!orderIsTerminal} />
          <InvoiceCard orderId={order.id} deliveredAt={order.delivered_at} customerId={order.customer_id} />
        </div>

        <div className="flex flex-col gap-4">
          <TasksChecklist orderId={order.id} />
          {!isReady && (
            <>
              <PartLinesSection orderId={order.id} />
              <LaborLinesSection orderId={order.id} />
              <MoneyCard
                estimatedTotal={order.estimated_total}
                paidAmount={order.paid_amount}
                balance={order.balance}
              />
            </>
          )}
          <AccessoriesListSection orderId={order.id} />
          <PhotosGrid orderId={order.id} />
          {/* Issue 34: history lives in the timeline below now — this stays
              only as the add-a-contact form, no duplicate list. */}
          <ContactsSection orderId={order.id} showHistory={false} />
        </div>
      </div>

      <TimelineSection orderId={order.id} />
    </div>
  );
}
