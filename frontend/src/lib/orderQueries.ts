import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";

/** One refresh for every view an order change can leave stale: the orders
 * list/board, the dashboard counts and the order page itself. With the global
 * 30 s staleTime (main.tsx) a view that isn't invalidated keeps rendering the
 * old order — PO bugs #23/#30: status changed from the orders list, the order
 * page still showed the previous status; a new order was missing from the
 * list. Pass `orderId` when it's known; without it every cached order page is
 * marked stale (inactive ones refetch only when next opened). */
export function invalidateOrderViews(queryClient: QueryClient, orderId?: string) {
  const detail = orderId
    ? [
        queryClient.invalidateQueries({ queryKey: queryKeys.order(orderId), exact: true }),
        queryClient.invalidateQueries({ queryKey: queryKeys.orderTimeline(orderId) }),
      ]
    : [queryClient.invalidateQueries({ queryKey: queryKeys.allOrderDetails })];
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.allOrders }),
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard }),
    ...detail,
  ]);
}
