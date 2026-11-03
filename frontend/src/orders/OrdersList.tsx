/**
 * OrdersList (order-workflow-revamp WP-K, docs/02 §16): the single orders
 * table, replacing both the Kanban board and the old status-grouped mobile
 * list. A real `<table>` on desktop, the same rows as stacked cards on
 * phone (Q19b) — one component, two renderings of the same sorted/filtered
 * data, toggled by breakpoint only (same `hidden md:block` / `md:hidden`
 * pattern this page used for Kanban/list before).
 *
 * No status-change controls here — status changes happen only on the order
 * page now (Q19b); `OrderStatusActions` (the old inline list buttons) is
 * retired along with Kanban's drag-and-drop.
 */

import { Link } from "react-router-dom";
import { Avatar } from "../components/Avatar";
import { t } from "../i18n/bg";
import { statusName } from "../lib/statusMatrix";
import type { OrderListItem, UserItem } from "./types";

function daysInStatus(statusChangedAt: string | null): number | null {
  if (!statusChangedAt) return null;
  const ms = Date.now() - new Date(statusChangedAt).getTime();
  return Math.max(0, Math.floor(ms / (1000 * 60 * 60 * 24)));
}

function formatPromisedOn(promisedOn: string | null): string {
  return promisedOn ? new Date(promisedOn).toLocaleDateString("bg-BG") : "—";
}

/** Default order (docs/02 §16): overdue first, then longest in the current
 * status. Exported for the unit test and kept pure (no fetch, no state) so
 * OrdersPage can apply it right after the query resolves. */
export function sortOrders(orders: OrderListItem[]): OrderListItem[] {
  return [...orders].sort((a, b) => {
    if (a.overdue !== b.overdue) return a.overdue ? -1 : 1;
    const aTime = a.status_changed_at ? new Date(a.status_changed_at).getTime() : 0;
    const bTime = b.status_changed_at ? new Date(b.status_changed_at).getTime() : 0;
    return aTime - bTime; // older status_changed_at = longer in status = first
  });
}

function Badges({ order }: { order: OrderListItem }) {
  return (
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
  );
}

function OrderTableRow({ order, technicianName }: { order: OrderListItem; technicianName: string | null }) {
  const days = daysInStatus(order.status_changed_at);
  return (
    <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
      <td className="whitespace-nowrap px-3 py-3">
        <Link to={`/orders/${order.id}`} className="font-medium text-blue-700 hover:underline">
          № {order.number}
        </Link>
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-slate-700">{statusName(order.status_code)}</td>
      <td className="px-3 py-3 text-slate-700">{order.customer_name}</td>
      <td className="px-3 py-3 text-slate-700">{order.asset_label}</td>
      <td className="whitespace-nowrap px-3 py-3">
        <div className="flex items-center gap-2">
          <Avatar name={technicianName ?? t("orders.technician_unassigned")} />
          <span className="text-slate-700">{technicianName ?? t("orders.technician_unassigned")}</span>
        </div>
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-slate-500">
        {days !== null ? t("orders.days_in_status", { days }) : "—"}
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-slate-500">{formatPromisedOn(order.promised_on)}</td>
      <td className="px-3 py-3">
        <Badges order={order} />
      </td>
    </tr>
  );
}

function OrderCardRow({ order, technicianName }: { order: OrderListItem; technicianName: string | null }) {
  const days = daysInStatus(order.status_changed_at);
  return (
    <li className="flex flex-col gap-2 border-b border-slate-100 px-3 py-3 last:border-0">
      <div className="flex items-start justify-between gap-2">
        <div>
          <Link to={`/orders/${order.id}`} className="font-semibold text-slate-900 hover:underline">
            № {order.number}
          </Link>
          <p className="text-sm text-slate-600">{order.customer_name} · {order.asset_label}</p>
          <p className="text-sm text-slate-500">{statusName(order.status_code)}</p>
        </div>
        <Avatar name={technicianName ?? t("orders.technician_unassigned")} />
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        {days !== null && <span>{t("orders.days_in_status", { days })}</span>}
        <span>{formatPromisedOn(order.promised_on)}</span>
      </div>
      <Badges order={order} />
    </li>
  );
}

export function OrdersList({
  orders,
  technicians,
}: {
  orders: OrderListItem[];
  technicians: UserItem[];
}) {
  const technicianNames = new Map(technicians.map((u) => [u.id, u.name]));
  const sorted = sortOrders(orders);
  const nameFor = (order: OrderListItem) =>
    order.technician_id ? technicianNames.get(order.technician_id) ?? null : null;

  return (
    <>
      <div className="hidden overflow-x-auto rounded-lg border border-slate-200 bg-white md:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <th className="px-3 py-2 font-semibold">{t("orders.column_number")}</th>
              <th className="px-3 py-2 font-semibold">{t("orders.column_status")}</th>
              <th className="px-3 py-2 font-semibold">{t("orders.column_customer")}</th>
              <th className="px-3 py-2 font-semibold">{t("orders.column_asset")}</th>
              <th className="px-3 py-2 font-semibold">{t("orders.column_technician")}</th>
              <th className="px-3 py-2 font-semibold">{t("orders.column_days_in_status")}</th>
              <th className="px-3 py-2 font-semibold">{t("orders.column_promised")}</th>
              <th className="px-3 py-2 font-semibold" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((order) => (
              <OrderTableRow key={order.id} order={order} technicianName={nameFor(order)} />
            ))}
          </tbody>
        </table>
      </div>

      <ul className="rounded-lg border border-slate-200 bg-white md:hidden">
        {sorted.map((order) => (
          <OrderCardRow key={order.id} order={order} technicianName={nameFor(order)} />
        ))}
      </ul>
    </>
  );
}
