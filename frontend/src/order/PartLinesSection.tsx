/** PartLines (docs/15 §6.5): per-line state selector, direct-select (not
 * cycling) - Wave 2 Issue 33 simplified V1 model: ordered/installed only, no
 * server-side transition restriction (docs/02 §7 — no inventory, states are
 * presentation only). "ordered" means assigned/requested for this order,
 * regardless of whether it's physically in stock yet. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

interface PartLineOut {
  id: string;
  name: string;
  qty: number;
  unit_cost: number;
  unit_price: number;
  state: string;
  // Issue 05 (audit correction, 2026-09-25): months, not days — the PO's
  // own examples ("12 месеца", "6 месеца"). Order-level (labor) warranty is
  // untouched, still days (CompletionDialog's own field).
  warranty_months: number | null;
}

// NULL = not specified (render nothing), 0 = explicitly no warranty, N = months.
function warrantyLabel(months: number | null): string | null {
  if (months === null) return null;
  if (months === 0) return t("order.part_warranty_none");
  return months === 1
    ? t("order.part_warranty_month_one")
    : t("order.part_warranty_months", { months });
}

// The 2 states the domain model accepts (backend/service_orders/lines.py
// PART_STATES) - the backend has no from->to transition matrix for part
// lines (unlike order status), so either state is always a valid target.
const STATES = ["ordered", "installed"] as const;
const STATE_LABEL: Record<string, Parameters<typeof t>[0]> = {
  ordered: "order.part_state_ordered",
  installed: "order.part_state_installed",
};

export function PartLinesSection({ orderId }: { orderId: string }) {
  const { me } = useAuth();
  // Wave 4 Issue 38: prefill new parts from the company default — never
  // forced, the field stays a plain editable number input either way.
  // Issue 05: the company setting (`parts_days`) is still stored/edited in
  // days (docs/business-os company-settings screen) — convert to months
  // here, at the one point a days-shaped value meets this months-shaped
  // input, same 30-days/month rule as the backend's own conversion.
  const partsDefaultDays = me?.warranty_defaults?.parts_days ?? null;
  const partsDefaultMonths = partsDefaultDays !== null ? Math.round(partsDefaultDays / 30) : null;
  const defaultInput = partsDefaultMonths !== null ? String(partsDefaultMonths) : "";

  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [warrantyMonths, setWarrantyMonths] = useState(defaultInput);
  // Tracked per line-id so one row's in-flight mutation never disables or
  // otherwise affects any other row's selector.
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();
  const pushToast = useToast();
  const key = queryKeys.orderPartLines(orderId);

  // `me` (and its warranty_defaults) may still be loading at first render —
  // catch up once it arrives, but only while the field is still untouched
  // ("" and the user hasn't typed anything of their own yet).
  useEffect(() => {
    setWarrantyMonths((prev) => (prev === "" ? defaultInput : prev));
  }, [defaultInput]);

  const { data: lines } = useQuery({
    queryKey: key,
    queryFn: () => api.get<PartLineOut[]>(`/orders/${orderId}/part-lines`),
  });

  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: key }),
      queryClient.invalidateQueries({ queryKey: queryKeys.order(orderId) }),
    ]);

  const addLine = async () => {
    if (!name.trim()) return;
    await api.post(`/orders/${orderId}/part-lines`, {
      name: name.trim(), unit_price: price.trim() ? Number(price) : 0,
      warranty_months: warrantyMonths.trim() ? Number(warrantyMonths) : null,
    });
    setName(""); setPrice(""); setWarrantyMonths(defaultInput);
    await invalidate();
  };

  const changeState = async (line: PartLineOut, nextState: string) => {
    if (nextState === line.state || pendingIds.has(line.id)) return;
    setPendingIds((prev) => new Set(prev).add(line.id));
    try {
      await api.patch(`/part-lines/${line.id}`, { state: nextState });
      await invalidate();
    } catch (err) {
      pushToast("error", err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setPendingIds((prev) => {
        const next = new Set(prev);
        next.delete(line.id);
        return next;
      });
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.part_lines")}
      </h3>
      <ul className="mb-3 flex flex-col gap-2">
        {(lines ?? []).map((line) => (
          <li key={line.id} className="flex items-center justify-between gap-2 text-sm">
            <span>
              <span className="font-medium text-slate-800">{line.name}</span>
              {" · "}
              <span className="text-slate-500">{line.unit_price.toFixed(2)} €</span>
              {warrantyLabel(line.warranty_months) !== null && (
                <>
                  {" · "}
                  <span className="text-slate-500">{warrantyLabel(line.warranty_months)}</span>
                </>
              )}
            </span>
            <select
              aria-label={`${t("order.part_status_label")} — ${line.name}`}
              value={line.state}
              disabled={pendingIds.has(line.id)}
              onChange={(e) => void changeState(line, e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-60 min-h-touch"
            >
              {STATES.map((s) => (
                <option key={s} value={s}>{t(STATE_LABEL[s])}</option>
              ))}
            </select>
          </li>
        ))}
        {lines?.length === 0 && <p className="text-sm text-slate-400">{t("order.part_lines_none")}</p>}
      </ul>
      <div className="flex gap-2">
        <input
          type="text" value={name} onChange={(e) => setName(e.target.value)}
          placeholder={t("order.part_name_placeholder")}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
        />
        <input
          type="number" min={0} step="0.01" value={price} onChange={(e) => setPrice(e.target.value)}
          placeholder="€" className="w-20 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
        />
        <input
          type="number" min={0} value={warrantyMonths}
          onChange={(e) => setWarrantyMonths(e.target.value)}
          aria-label={t("order.part_warranty_months_label")}
          title={t("order.part_warranty_months_label")}
          placeholder={t("order.part_warranty_months_label")}
          className="w-24 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
        />
        <button
          type="button" onClick={() => void addLine()}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch"
        >
          {t("intake.accessory_add")}
        </button>
      </div>
    </div>
  );
}
