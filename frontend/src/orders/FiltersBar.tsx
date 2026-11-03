/** FiltersBar (order-workflow-revamp WP-K, docs/02 §16): status chips
 * ("Всички отворени" + each open status) plus Техник · Приоритет ·
 * Просрочени. The Kanban/list view toggle that used to live here is gone —
 * the orders table is the only view now (Q19). */

import { t } from "../i18n/bg";
import { OPEN_STATUSES } from "../lib/statusMatrix";
import type { UserItem } from "./types";

export interface OrderFilters {
  statusCode: string; // "" = Всички отворени
  technicianId: string;
  priorityHigh: boolean;
  overdue: boolean;
}

export function FiltersBar({
  filters,
  onChange,
  technicians,
}: {
  filters: OrderFilters;
  onChange: (filters: OrderFilters) => void;
  technicians: UserItem[];
}) {
  return (
    <div className="mb-4 flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          aria-pressed={filters.statusCode === ""}
          onClick={() => onChange({ ...filters, statusCode: "" })}
          className={`rounded-full px-3 py-1.5 text-sm font-medium min-h-touch ${
            filters.statusCode === ""
              ? "bg-blue-600 text-white"
              : "border border-slate-300 text-slate-600 hover:bg-slate-50"
          }`}
        >
          {t("orders.filter_status_all")}
        </button>
        {OPEN_STATUSES.map((s) => (
          <button
            key={s.code}
            type="button"
            aria-pressed={filters.statusCode === s.code}
            onClick={() => onChange({ ...filters, statusCode: s.code })}
            className={`rounded-full px-3 py-1.5 text-sm font-medium min-h-touch ${
              filters.statusCode === s.code
                ? "bg-blue-600 text-white"
                : "border border-slate-300 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {s.name_bg}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={filters.technicianId}
          onChange={(e) => onChange({ ...filters, technicianId: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm min-h-touch"
        >
          <option value="">{t("orders.filter_technician_all")}</option>
          {technicians.map((u) => (
            <option key={u.id} value={u.id}>{u.name}</option>
          ))}
        </select>

        <button
          type="button"
          aria-pressed={filters.priorityHigh}
          onClick={() => onChange({ ...filters, priorityHigh: !filters.priorityHigh })}
          className={`rounded-lg border px-3 py-2 text-sm font-medium min-h-touch ${
            filters.priorityHigh
              ? "border-orange-600 bg-orange-50 text-orange-700"
              : "border-slate-300 text-slate-600 hover:bg-slate-50"
          }`}
        >
          {t("orders.filter_priority_high")}
        </button>

        <button
          type="button"
          aria-pressed={filters.overdue}
          onClick={() => onChange({ ...filters, overdue: !filters.overdue })}
          className={`rounded-lg border px-3 py-2 text-sm font-medium min-h-touch ${
            filters.overdue
              ? "border-red-600 bg-red-50 text-red-700"
              : "border-slate-300 text-slate-600 hover:bg-slate-50"
          }`}
        >
          {t("orders.filter_overdue")}
        </button>
      </div>
    </div>
  );
}
