/** PartLines (docs/15 §6.5): state chips needed→ordered→received→installed
 * (docs/02 §7 — no inventory, states drive the Чака части flow). */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

interface PartLineOut {
  id: string;
  name: string;
  qty: number;
  unit_cost: number;
  unit_price: number;
  state: string;
}

const STATES = ["needed", "ordered", "received", "installed"] as const;
const STATE_LABEL: Record<string, Parameters<typeof t>[0]> = {
  needed: "order.part_state_needed",
  ordered: "order.part_state_ordered",
  received: "order.part_state_received",
  installed: "order.part_state_installed",
  removed: "order.part_state_removed",
};

export function PartLinesSection({ orderId }: { orderId: string }) {
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const queryClient = useQueryClient();
  const key = queryKeys.orderPartLines(orderId);

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
    });
    setName(""); setPrice("");
    await invalidate();
  };

  const cycleState = async (line: PartLineOut) => {
    const idx = STATES.indexOf(line.state as (typeof STATES)[number]);
    const next = STATES[Math.min(idx + 1, STATES.length - 1)];
    if (next === line.state) return;
    await api.patch(`/part-lines/${line.id}`, { state: next });
    await invalidate();
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.part_lines")}
      </h3>
      <ul className="mb-3 flex flex-col gap-2">
        {(lines ?? []).map((line) => (
          <li key={line.id} className="flex items-center justify-between gap-2 text-sm">
            <span className="text-slate-700">{line.name} · {line.unit_price.toFixed(2)} €</span>
            <button
              type="button"
              onClick={() => void cycleState(line)}
              disabled={line.state === "installed" || line.state === "removed"}
              className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200 disabled:opacity-60"
            >
              {t(STATE_LABEL[line.state] ?? "order.part_state_needed")}
            </button>
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
