/** OrdersList (docs/15 §6.3): mobile <md or ?view=list fallback — StatusGroup
 * → OrderRow + StatusButtons (buttons are the primary path per docs/10 §2.2). */

import { Link } from "react-router-dom";
import { Avatar } from "../components/Avatar";
import { t } from "../i18n/bg";
import { OPEN_STATUSES, statusName } from "../lib/statusMatrix";
import { OrderStatusActions } from "./OrderStatusActions";
import type { OrderListItem, UserItem } from "./types";

function OrderRow({
  order,
  technicianName,
  onChanged,
}: {
  order: OrderListItem;
  technicianName: string | null;
  onChanged: () => void;
}) {
  return (
    <li className="flex flex-col gap-2 border-b border-slate-100 px-3 py-3 last:border-0">
      <div className="flex items-start justify-between gap-2">
        <div>
          <Link to={`/orders/${order.id}`} className="font-semibold text-slate-900 hover:underline">
            № {order.number}
          </Link>
          <p className="text-sm text-slate-600">{order.customer_name} · {order.asset_label}</p>
          <p className="line-clamp-1 text-sm text-slate-500">{order.complaint}</p>
        </div>
        <Avatar name={technicianName ?? t("orders.technician_unassigned")} />
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {order.overdue && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
            {t("orders.badge_overdue")}
          </span>
        )}
        {order.priority === "high" && (
          <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700">
            {t("orders.badge_priority")}
          </span>
        )}
        {order.origin_order_id && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
            {t("orders.badge_warranty")}
          </span>
        )}
      </div>
      <OrderStatusActions orderId={order.id} statusCode={order.status_code} onChanged={onChanged} />
    </li>
  );
}

export function OrdersList({
  orders,
  technicians,
  onChanged,
}: {
  orders: OrderListItem[];
  technicians: UserItem[];
  onChanged: () => void;
}) {
  const technicianNames = new Map(technicians.map((u) => [u.id, u.name]));

  return (
    <div className="flex flex-col gap-4">
      {OPEN_STATUSES.map((status) => {
        const group = orders.filter((o) => o.status_code === status.code);
        if (group.length === 0) return null;
        return (
          <div key={status.code} className="rounded-lg border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-3 py-2">
              <h2 className="text-sm font-semibold text-slate-700">
                {statusName(status.code)} ({group.length})
              </h2>
            </div>
            <ul>
              {group.map((order) => (
                <OrderRow
                  key={order.id}
                  order={order}
                  technicianName={order.technician_id ? technicianNames.get(order.technician_id) ?? null : null}
                  onChanged={onChanged}
                />
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
