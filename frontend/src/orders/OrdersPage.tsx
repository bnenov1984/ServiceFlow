/**
 * OrdersPage (docs/15 §6.3, Wave 2 Issue 3; table-only since order-workflow-
 * revamp WP-K): DashboardSummary + FiltersBar + the single OrdersList table
 * — Kanban and the list/kanban toggle are gone (Q19), and so is every
 * status-changing control that used to live here (drag-and-drop, inline row
 * buttons) — status changes happen only on the order page now (Q19b).
 * Data: GET /dashboard (inside DashboardSummary) + GET /orders?state=open +
 * GET /users.
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { DashboardSummary } from "../dashboard/DashboardSummary";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { FiltersBar, type OrderFilters } from "./FiltersBar";
import { OrdersList } from "./OrdersList";
import type { OrderListItem, UserItem } from "./types";

const EMPTY_FILTERS: OrderFilters = {
  statusCode: "", technicianId: "", priorityHigh: false, overdue: false,
};

export function OrdersPage() {
  const navigate = useNavigate();
  const { me } = useAuth();
  // Dashboard deep-links (docs/15 §6.2 widget → filtered /orders): ?status
  // pins a status_code, ?overdue=1 seeds the existing overdue toggle. Re-sync
  // both from the URL on every change, not just once at mount — a widget
  // click while already on this page must re-apply the filter, not no-op.
  const [searchParams] = useSearchParams();
  // Issue 6: an Owner's default view is every order (unchanged); a non-owner
  // (technician) defaults to their own orders — reusing the existing
  // technician_id filter and their own authenticated user_id, not a new role
  // system. The technician <select> already lets anyone (Owner or not) pick
  // "Всички техници" or a colleague, so switching to view/cover another
  // technician's orders needs no new control.
  const [filters, setFilters] = useState<OrderFilters>(() => ({
    ...EMPTY_FILTERS,
    statusCode: searchParams.get("status") ?? "",
    technicianId: me && !me.is_owner ? me.user_id : "",
    overdue: searchParams.get("overdue") === "1",
  }));
  useEffect(() => {
    const statusCode = searchParams.get("status") ?? "";
    const overdue = searchParams.get("overdue") === "1";
    setFilters((prev) =>
      prev.statusCode === statusCode && prev.overdue === overdue
        ? prev
        : { ...prev, statusCode, overdue },
    );
  }, [searchParams]);

  const params = useMemo(() => {
    const p: Record<string, string> = { state: "open" };
    if (filters.statusCode) p.status_code = filters.statusCode;
    if (filters.technicianId) p.technician_id = filters.technicianId;
    if (filters.priorityHigh) p.priority = "high";
    if (filters.overdue) p.overdue = "true";
    return p;
  }, [filters]);

  const {
    data: orders, isLoading, isError, error, refetch,
  } = useQuery({
    queryKey: queryKeys.orders(params),
    queryFn: () => api.get<OrderListItem[]>(`/orders?${new URLSearchParams(params).toString()}`),
  });

  const { data: users } = useQuery({
    queryKey: queryKeys.users,
    queryFn: () => api.get<UserItem[]>("/users"),
  });
  const technicians = (users ?? []).filter((u) => u.is_active);

  if (isLoading) {
    return (
      <div>
        <h1 className="mb-4 text-2xl font-bold text-slate-900">{t("nav.orders")}</h1>
        <DashboardSummary />
        <div className="flex flex-col gap-2">
          <Skeleton className="h-10 w-full" />
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div>
        <h1 className="mb-4 text-2xl font-bold text-slate-900">{t("nav.orders")}</h1>
        <DashboardSummary />
        <ErrorState
          text={error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal")}
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  const list = orders ?? [];

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold text-slate-900">{t("nav.orders")}</h1>
      <DashboardSummary />
      <FiltersBar filters={filters} onChange={setFilters} technicians={technicians} />

      {list.length === 0 ? (
        <EmptyState
          text={t("orders.empty")}
          action={
            <button
              type="button"
              onClick={() => navigate("/orders/new")}
              className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 min-h-touch"
            >
              {t("shell.new_order")}
            </button>
          }
        />
      ) : (
        <OrdersList orders={list} technicians={technicians} />
      )}
    </div>
  );
}
