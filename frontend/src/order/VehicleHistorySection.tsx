/**
 * VehicleHistorySection (Wave 3 Issues 21/26/27, docs/business-os Wave 3
 * audit): the smallest useful "service history" view — every visit against
 * this vehicle's asset_id, across every customer it has ever been owned by
 * (Issue 20), using only data the order already carries. No analytics, no
 * charts, no predictions — a compact list.
 */

import { useQuery } from "@tanstack/react-query";
import { type ServiceHistoryEntry, VehicleVisitList } from "../components/VehicleVisitList";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

interface AssetServiceHistoryOut {
  asset_id: string;
  asset_label: string;
  current_mileage: number | null;
  visits: ServiceHistoryEntry[];
}

export function VehicleHistorySection({
  assetId,
  currentOrderId,
}: {
  assetId: string;
  currentOrderId: string;
}) {
  const { data } = useQuery({
    queryKey: queryKeys.assetServiceHistory(assetId),
    queryFn: () => api.get<AssetServiceHistoryOut>(`/assets/${assetId}/service-history`),
  });

  const otherVisits = (data?.visits ?? []).filter((v) => v.order_id !== currentOrderId);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.vehicle_history")}
      </h3>
      <VehicleVisitList visits={otherVisits} emptyLabel={t("order.vehicle_history_empty")} />
    </div>
  );
}
