/** LaborLines (docs/15 §6.5, docs/02 §8): fixed-price lines (qty × unit_price). */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

interface LaborLineOut {
  id: string;
  description: string;
  qty: number;
  unit_price: number;
}

export function LaborLinesSection({ orderId }: { orderId: string }) {
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const queryClient = useQueryClient();
  const key = queryKeys.orderLaborLines(orderId);

  const { data: lines } = useQuery({
    queryKey: key,
    queryFn: () => api.get<LaborLineOut[]>(`/orders/${orderId}/labor-lines`),
  });

  const addLine = async () => {
    if (!description.trim()) return;
    await api.post(`/orders/${orderId}/labor-lines`, {
      description: description.trim(), unit_price: price.trim() ? Number(price) : 0,
    });
    setDescription(""); setPrice("");
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: key }),
      queryClient.invalidateQueries({ queryKey: queryKeys.order(orderId) }),
    ]);
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.labor_lines")}
      </h3>
      <ul className="mb-3 flex flex-col gap-1">
        {(lines ?? []).map((line) => (
          <li key={line.id} className="text-sm text-slate-700">
            {line.description} · {line.unit_price.toFixed(2)} €
          </li>
        ))}
        {lines?.length === 0 && <p className="text-sm text-slate-400">{t("order.labor_lines_none")}</p>}
      </ul>
      <div className="flex gap-2">
        <input
          type="text" value={description} onChange={(e) => setDescription(e.target.value)}
          placeholder={t("order.labor_description_placeholder")}
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
