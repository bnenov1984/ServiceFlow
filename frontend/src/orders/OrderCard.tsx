/** Kanban card (docs/15 §6.3): № · клиент · актив · 1-ред оплакване · инициали
 * техник · days-in-status chip · badges Просрочена/Приоритет/Гаранционна. */

import { useDraggable } from "@dnd-kit/core";
import { Link } from "react-router-dom";
import { Avatar } from "../components/Avatar";
import { t } from "../i18n/bg";
import { statusName } from "../lib/statusMatrix";
import type { OrderListItem } from "./types";

function daysInStatus(statusChangedAt: string | null): number | null {
  if (!statusChangedAt) return null;
  const ms = Date.now() - new Date(statusChangedAt).getTime();
  return Math.max(0, Math.floor(ms / (1000 * 60 * 60 * 24)));
}

export function OrderCard({
  order,
  technicianName,
}: {
  order: OrderListItem;
  technicianName: string | null;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: order.id,
    data: { statusCode: order.status_code },
  });
  const days = daysInStatus(order.status_changed_at);

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      style={transform ? { transform: `translate(${transform.x}px, ${transform.y}px)` } : undefined}
      className={`flex flex-col gap-1.5 rounded-lg border border-slate-200 bg-white p-3 shadow-sm ${
        isDragging ? "z-10 opacity-90 shadow-lg" : ""
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <Link
          to={`/orders/${order.id}`}
          onClick={(e) => e.stopPropagation()}
          className="font-semibold text-slate-900 hover:underline"
        >
          № {order.number}
        </Link>
        <Avatar name={technicianName ?? t("orders.technician_unassigned")} />
      </div>
      <p className="text-sm font-medium text-slate-700">{order.customer_name}</p>
      <p className="text-xs text-slate-500">{order.asset_label}</p>
      <p className="line-clamp-1 text-sm text-slate-600">{order.complaint}</p>

      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        {order.status_code === "waiting_customer" && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
            {statusName("waiting_customer")}
          </span>
        )}
        {days !== null && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
            {t("orders.days_in_status", { days })}
          </span>
        )}
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
    </div>
  );
}
