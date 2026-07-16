/** ActiveOrders / History (docs/15 §6.7): the customer's orders split by
 * open/terminal state, each row linking to the order detail screen. */

import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { StatusPill } from "../components/StatusPill";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { OrderListItem } from "../orders/types";

export function CustomerOrdersSection({
  customerId,
  state,
  title,
  emptyText,
}: {
  customerId: string;
  state: "open" | "terminal";
  title: string;
  emptyText: string;
}) {
  const { data: orders } = useQuery({
    queryKey: queryKeys.customerOrders(customerId, state),
    queryFn: () =>
      api.get<OrderListItem[]>(`/orders?state=${state}&customer_id=${customerId}`),
  });

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {orders && orders.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {orders.map((order) => (
            <li key={order.id}>
              <Link
                to={`/orders/${order.id}`}
                className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2 hover:bg-slate-50 min-h-touch"
              >
                <div>
                  <p className="font-medium text-slate-800">№ {order.number}</p>
                  <p className="line-clamp-1 text-sm text-slate-500">{order.complaint}</p>
                </div>
                <StatusPill code={order.status_code} />
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-400">{emptyText}</p>
      )}
    </div>
  );
}
