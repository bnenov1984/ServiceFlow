/** Shared per-visit list markup (WP-E's VehicleHistorySection originally,
 * now also used at intake — WP-C #20) — a compact "order № · date ·
 * customer · status · mileage · complaint" row, nothing more. */

import { Link } from "react-router-dom";
import { t } from "../i18n/bg";
import { statusName } from "../lib/statusMatrix";

export interface ServiceHistoryEntry {
  order_id: string;
  order_number: string;
  created_at: string;
  status_code: string;
  customer_id: string;
  customer_name: string;
  complaint: string;
  mileage: number | null;
}

export function VehicleVisitList({
  visits,
  emptyLabel,
}: {
  visits: ServiceHistoryEntry[];
  emptyLabel: string;
}) {
  if (visits.length === 0) {
    return <p className="text-sm text-slate-400">{emptyLabel}</p>;
  }
  return (
    <ul className="flex flex-col gap-2">
      {visits.map((v) => (
        <li key={v.order_id} className="rounded-lg border border-slate-100 px-3 py-2 text-sm">
          <div className="flex items-center justify-between gap-2">
            <Link to={`/orders/${v.order_id}`} className="font-medium text-blue-700 hover:underline">
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
  );
}
