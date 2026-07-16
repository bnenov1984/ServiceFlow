/**
 * DashboardPage (docs/15 §6.2): WidgetGrid of 6 StatWidgets over GET /dashboard
 * (one call). Each widget links into a filtered /orders view (§6.3 deep-link
 * params). Loading: 6 skeleton cards. Error: one ErrorState + Retry. Empty
 * (everything 0): a calm, friendly line instead of a grid of zeros.
 */

import { useQuery } from "@tanstack/react-query";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
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

export function DashboardPage() {
  const {
    data, isLoading, isError, error, refetch,
  } = useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: () => api.get<DashboardOut>("/dashboard"),
  });

  if (isLoading) {
    return (
      <div>
        <h1 className="mb-4 text-2xl font-bold text-slate-900">{t("nav.dashboard")}</h1>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div>
        <h1 className="mb-4 text-2xl font-bold text-slate-900">{t("nav.dashboard")}</h1>
        <ErrorState
          text={error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal")}
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  const allZero =
    data.active_orders === 0 &&
    data.waiting_parts === 0 &&
    data.ready.count === 0 &&
    data.overdue === 0 &&
    data.today_tasks === 0 &&
    data.call_tasks === 0;

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold text-slate-900">{t("nav.dashboard")}</h1>
      {allZero ? (
        <EmptyState text={t("dashboard.empty")} />
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
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
          <StatWidget
            to="/orders?overdue=1"
            label={t("dashboard.widget_overdue")}
            value={data.overdue}
          />
          <StatWidget to="/orders" label={t("dashboard.widget_today_tasks")} value={data.today_tasks} />
          <StatWidget to="/orders" label={t("dashboard.widget_call_tasks")} value={data.call_tasks} />
        </div>
      )}
    </div>
  );
}
