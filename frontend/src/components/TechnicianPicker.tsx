/**
 * Technician picker with workload (WP-F, PO items #15/#16, decision Q22):
 * every active user (Owner included) with their count of orders in
 * Диагностика + Ремонт; free users first and tagged „свободен" — a highlight,
 * not a filter. Names come from identity's GET /users, counts from
 * RepairFlow's GET /orders/technician-load (C-6). If the counts fail to load,
 * the picker still lists names, so intake is never blocked.
 */

import { useQuery } from "@tanstack/react-query";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

interface UserOut {
  id: string;
  name: string;
  is_active: boolean;
}

interface TechnicianLoadOut {
  technician_id: string;
  active_count: number;
}

export interface TechnicianOption {
  id: string;
  label: string;
}

function labelFor(name: string, count: number | undefined): string {
  if (count === undefined) return name;
  if (count === 0) return t("intake.technician_free", { name });
  if (count === 1) return t("intake.technician_active_one", { name });
  return t("intake.technician_active_many", { name, count });
}

/** Active users sorted by load (free first), then by name. `load` undefined
 * means the counts are unavailable: plain names, sorted by name. */
export function technicianOptions(
  users: UserOut[], load: TechnicianLoadOut[] | undefined,
): TechnicianOption[] {
  const counts = load ? new Map(load.map((l) => [l.technician_id, l.active_count])) : null;
  const countOf = (id: string) => (counts ? counts.get(id) ?? 0 : undefined);
  return users
    .filter((u) => u.is_active)
    .sort((a, b) => (countOf(a.id) ?? 0) - (countOf(b.id) ?? 0) || a.name.localeCompare(b.name, "bg"))
    .map((u) => ({ id: u.id, label: labelFor(u.name, countOf(u.id)) }));
}

export function TechnicianPicker({
  value, onChange, className,
}: {
  value: string | null;
  onChange: (technicianId: string | null) => void;
  className?: string;
}) {
  const { data: users } = useQuery({
    queryKey: queryKeys.users,
    queryFn: () => api.get<UserOut[]>("/users"),
  });
  const { data: load } = useQuery({
    queryKey: queryKeys.technicianLoad,
    queryFn: () => api.get<TechnicianLoadOut[]>("/orders/technician-load"),
  });

  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
      className={className}
    >
      <option value="">{t("intake.technician_unassigned")}</option>
      {technicianOptions(users ?? [], load).map((o) => (
        <option key={o.id} value={o.id}>{o.label}</option>
      ))}
    </select>
  );
}
