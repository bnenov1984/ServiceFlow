/**
 * OrdersPage (docs/15 §6.3, Wave 2 Issue 3): DashboardSummary + FiltersBar +
 * KanbanBoard (desktop) / OrdersList (mobile or ?view=list) — the merged
 * "one main screen" (compact summary on top, Orders workspace below).
 * Data: GET /dashboard (inside DashboardSummary) + GET /orders?state=open +
 * GET /users.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { useToast } from "../components/Toast";
import { DashboardSummary } from "../dashboard/DashboardSummary";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { invalidateOrderViews } from "../lib/orderQueries";
import { queryKeys } from "../lib/queryKeys";
import { ApprovalDialog } from "../order/dialogs/ApprovalDialog";
import { FiltersBar, type OrderFilters } from "./FiltersBar";
import { KanbanBoard } from "./KanbanBoard";
import { OrdersList } from "./OrdersList";
import type { OrderListItem, UserItem } from "./types";

const EMPTY_FILTERS: OrderFilters = { technicianId: "", priorityHigh: false, overdue: false };

export function OrdersPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const pushToast = useToast();
  const { me } = useAuth();
  // Dashboard deep-links (docs/15 §6.2 widget → filtered /orders): ?status
  // pins a status_code, ?overdue=1 seeds the existing overdue toggle. Now
  // that the summary widgets and this workspace are the same page (Issue 3),
  // a widget click no longer always causes a fresh mount — re-sync `overdue`
  // from the URL on every change, not just once at mount, or clicking
  // "Просрочени" a second time while already here would silently no-op.
  const [searchParams] = useSearchParams();
  const pinnedStatus = searchParams.get("status");
  // Issue 6: an Owner's default view is every order (unchanged); a non-owner
  // (technician) defaults to their own orders — reusing the existing
  // technician_id filter and their own authenticated user_id, not a new role
  // system. The technician <select> already lets anyone (Owner or not) pick
  // "Всички техници" or a colleague, so switching to view/cover another
  // technician's orders needs no new control.
  const [filters, setFilters] = useState<OrderFilters>(() => ({
    ...EMPTY_FILTERS,
    technicianId: me && !me.is_owner ? me.user_id : "",
    overdue: searchParams.get("overdue") === "1",
  }));
  useEffect(() => {
    const overdue = searchParams.get("overdue") === "1";
    setFilters((prev) => (prev.overdue === overdue ? prev : { ...prev, overdue }));
  }, [searchParams]);
  const [view, setView] = useState<"kanban" | "list">("kanban");
  const [pendingApproval, setPendingApproval] = useState<{ orderId: string; to: string } | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [approvalSubmitting, setApprovalSubmitting] = useState(false);

  const params = useMemo(() => {
    const p: Record<string, string> = { state: "open" };
    if (filters.technicianId) p.technician_id = filters.technicianId;
    if (filters.priorityHigh) p.priority = "high";
    if (filters.overdue) p.overdue = "true";
    if (pinnedStatus) p.status_code = pinnedStatus;
    return p;
  }, [filters, pinnedStatus]);

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

  const refreshOrders = () => {
    void invalidateOrderViews(queryClient);
  };

  const changeStatus = async (orderId: string, body: Record<string, unknown>) => {
    const result = await api.post<{ warning: string | null }>(`/orders/${orderId}/status`, body);
    refreshOrders();
    if (result.warning === "skip") pushToast("conflict", t("order.warning_skip"));
  };

  const handleDrop = (orderId: string, from: string, to: string) => {
    if (from === "waiting_customer") {
      setPendingApproval({ orderId, to });
      return;
    }
    void changeStatus(orderId, { to }).catch((err) => {
      pushToast("error", err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    });
  };

  const closeApproval = () => { setPendingApproval(null); setApprovalError(null); };

  const confirmApproval = async (channel: string, amount: number | null) => {
    if (!pendingApproval) return;
    setApprovalSubmitting(true);
    setApprovalError(null);
    try {
      await changeStatus(pendingApproval.orderId, {
        to: pendingApproval.to, approval: { approved: true, channel, amount },
      });
      closeApproval();
    } catch (err) {
      setApprovalError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setApprovalSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div>
        <h1 className="mb-4 text-2xl font-bold text-slate-900">{t("nav.orders")}</h1>
        <DashboardSummary />
        <div className="flex flex-col gap-4">
          <Skeleton className="h-10 w-full" />
          <div className="flex gap-3 overflow-x-auto">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-64 w-72 shrink-0" />
            ))}
          </div>
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
      <FiltersBar
        filters={filters}
        onChange={setFilters}
        technicians={technicians}
        view={view}
        onViewChange={setView}
      />

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
        <>
          {view === "kanban" && (
            <div className="hidden md:block">
              <KanbanBoard orders={list} technicians={technicians} onDrop={handleDrop} />
            </div>
          )}
          <div className={view === "kanban" ? "md:hidden" : ""}>
            <OrdersList orders={list} technicians={technicians} onChanged={refreshOrders} />
          </div>
        </>
      )}

      <ApprovalDialog
        open={pendingApproval !== null}
        onClose={closeApproval}
        onConfirm={(channel, amount) => void confirmApproval(channel, amount)}
        submitting={approvalSubmitting}
        error={approvalError}
      />
    </div>
  );
}
