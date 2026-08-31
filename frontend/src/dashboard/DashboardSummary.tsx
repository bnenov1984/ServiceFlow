/**
 * DashboardSummary (Wave 2 Issue 3): the same 6 GET /dashboard counts
 * DashboardPage used to render as its own full screen, now a compact strip
 * at the top of the merged Orders workspace (OrdersPage). No new data, no
 * new analytics — same query, same widgets, same deep-link targets
 * (StatWidget -> /orders?...), just without its own heading/full-page
 * loading-and-error chrome, since the page around it already has both.
 */

import { useQuery } from "@tanstack/react-query";
import { Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { StatWidget } from "./StatWidget";

interface ReadyWidget {
  count: number;
  over_limit: number;
}

interface DashboardOut {
  active_orders: number;
  waiting_parts: number;
  ready: ReadyWidget;
  overdue: number;
  today_tasks: number;
  call_tasks: number;
}

export function DashboardSummary() {
  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: () => api.get<DashboardOut>("/dashboard"),
  });

  if (isLoading) {
    return (
      <div className="mb-4 grid grid-cols-3 gap-2 md:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-16" />
        ))}
      </div>
    );
  }

  // A failed/empty summary never blocks the Orders workspace below it — this
  // strip is a convenience, not the page's primary content anymore.
  if (isError || !data) return null;

  const allZero =
    data.active_orders === 0 &&
    data.waiting_parts === 0 &&
    data.ready.count === 0 &&
    data.overdue === 0 &&
    data.today_tasks === 0 &&
    data.call_tasks === 0;
  if (allZero) return null;

  return (
    <div className="mb-4 grid grid-cols-3 gap-2 md:grid-cols-6">
      <StatWidget to="/orders" label={t("dashboard.widget_active")} value={data.active_orders} />
      <StatWidget
        to="/orders?status=waiting_parts"
        label={t("dashboard.widget_waiting_parts")}
        value={data.waiting_parts}
      />
      <StatWidget
        to="/orders?status=ready"
        label={t("dashboard.widget_ready")}
        value={data.ready.count}
        highlight={
          data.ready.over_limit > 0
            ? t("dashboard.widget_ready_over_limit", { count: data.ready.over_limit })
            : undefined
        }
      />
      <StatWidget to="/orders?overdue=1" label={t("dashboard.widget_overdue")} value={data.overdue} />
      <StatWidget to="/orders" label={t("dashboard.widget_today_tasks")} value={data.today_tasks} />
      <StatWidget to="/orders" label={t("dashboard.widget_call_tasks")} value={data.call_tasks} />
    </div>
  );
}
