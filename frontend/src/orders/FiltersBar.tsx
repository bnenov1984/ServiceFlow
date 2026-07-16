/** FiltersBar (docs/15 §6.3): Техник · Приоритет · Просрочени · view toggle. */

import { t } from "../i18n/bg";
import type { UserItem } from "./types";

export interface OrderFilters {
  technicianId: string;
  priorityHigh: boolean;
  overdue: boolean;
}

export function FiltersBar({
  filters,
  onChange,
  technicians,
  view,
  onViewChange,
}: {
  filters: OrderFilters;
  onChange: (filters: OrderFilters) => void;
  technicians: UserItem[];
  view: "kanban" | "list";
  onViewChange: (view: "kanban" | "list") => void;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
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

      <div className="ml-auto hidden gap-1 rounded-lg border border-slate-300 p-1 md:flex">
        <button
          type="button"
          aria-pressed={view === "kanban"}
          onClick={() => onViewChange("kanban")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium ${
            view === "kanban" ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          {t("orders.view_kanban")}
        </button>
        <button
          type="button"
          aria-pressed={view === "list"}
          onClick={() => onViewChange("list")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium ${
            view === "list" ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          {t("orders.view_list")}
        </button>
      </div>
    </div>
  );
}
