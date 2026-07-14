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
import { LaborLinesSection } from "./LaborLinesSection";
import { MoneyCard } from "./MoneyCard";
import { OrderHeader } from "./OrderHeader";
import { PartLinesSection } from "./PartLinesSection";
import { PhotosGrid } from "./PhotosGrid";
import { TasksChecklist } from "./TasksChecklist";
import { TimelineSection } from "./TimelineSection";

interface OrderDetailOut {
  id: string;
  number: string;
  customer_id: string;
  asset_id: string;
  complaint: string;
  status_code: string;
  archived: boolean;
  diagnosis: DiagnosisValue | null;
  estimated_total: number;
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
            />
          )}
          <ComplaintBlock orderId={order.id} complaint={order.complaint} editable={!orderIsTerminal} />
          <DiagnosisCard orderId={order.id} diagnosis={order.diagnosis} editable={!orderIsTerminal} />
          <MoneyCard estimatedTotal={order.estimated_total} />
        </div>

        <div className="flex flex-col gap-4">
          <TasksChecklist orderId={order.id} />
          <PartLinesSection orderId={order.id} />
          <LaborLinesSection orderId={order.id} />
          <AccessoriesListSection orderId={order.id} />
          <PhotosGrid orderId={order.id} />
          <ContactsSection orderId={order.id} />
        </div>
      </div>

      <TimelineSection orderId={order.id} />
    </div>
  );
}
