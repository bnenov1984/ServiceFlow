/**
 * VehicleHistorySection (Wave 3 Issues 21/26/27, docs/business-os Wave 3
 * audit): the smallest useful "service history" view — every visit against
 * this vehicle's asset_id, across every customer it has ever been owned by
 * (Issue 20), using only data the order already carries. No analytics, no
 * charts, no predictions — a compact list.
 */

import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { statusName } from "../lib/statusMatrix";

interface ServiceHistoryEntry {
  order_id: string;
  order_number: string;
  created_at: string;
  status_code: string;
  customer_id: string;
  customer_name: string;
  complaint: string;
  mileage: number | null;
}

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
      {otherVisits.length === 0 ? (
        <p className="text-sm text-slate-400">{t("order.vehicle_history_empty")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {otherVisits.map((v) => (
            <li key={v.order_id} className="rounded-lg border border-slate-100 px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                <Link
                  to={`/orders/${v.order_id}`}
                  className="font-medium text-blue-700 hover:underline"
                >
                  {v.order_number}
                </Link>
                <span className="text-slate-400">
                  {new Date(v.created_at).toLocaleDateString("bg-BG")}
                </span>
              </div>
              <p className="mt-0.5 text-slate-600">
                {v.customer_name} · {statusName(v.status_code)}
                {v.mileage != null ? ` · ${t("order.vehicle_history_mileage", { mileage: v.mileage })}` : ""}
              </p>
              <p className="mt-0.5 truncate text-slate-500">{v.complaint}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
