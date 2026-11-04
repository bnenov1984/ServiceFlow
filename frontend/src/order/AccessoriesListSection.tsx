/** AccessoriesList (docs/15 §6.5): persistent view of the intake checklist,
 * with returned-checkbox — shares its query cache with OrderHeader's
 * CompletionDialog (queryKeys.orderAccessories).
 *
 * order-workflow-revamp WP-H (Q16/Q16b): `accessoriesEnabled` is false for
 * automotive orders — the add-new form hides, but any already-existing
 * (historic) items keep showing and stay returnable. The section itself
 * renders nothing once there's neither an existing item nor a way to add
 * one, so an automotive order with no accessory history shows no empty
 * "Аксесоари" card at all. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

interface AccessoryOut {
  id: string;
  name: string;
  qty: number;
  returned: boolean;
}

export function AccessoriesListSection({
  orderId,
  accessoriesEnabled,
}: {
  orderId: string;
  accessoriesEnabled: boolean;
}) {
  const [name, setName] = useState("");
  const queryClient = useQueryClient();
  const key = queryKeys.orderAccessories(orderId);

  const { data: items } = useQuery({
    queryKey: key,
    queryFn: () => api.get<AccessoryOut[]>(`/orders/${orderId}/accessories`),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: key });

  const addItem = async () => {
    if (!name.trim()) return;
    await api.post(`/orders/${orderId}/accessories`, { name: name.trim() });
    setName("");
    await invalidate();
  };

  const toggleReturned = async (item: AccessoryOut) => {
    await api.patch(`/accessories/${item.id}`, { returned: !item.returned });
    await invalidate();
  };

  if (!accessoriesEnabled && items !== undefined && items.length === 0) return null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.accessories")}
      </h3>
      <ul className="mb-3 flex flex-col gap-1">
        {(items ?? []).map((item) => (
          <li key={item.id}>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={item.returned}
                onChange={() => void toggleReturned(item)}
                className="h-5 w-5"
              />
              <span className={item.returned ? "text-slate-400 line-through" : "text-slate-700"}>
                {item.name}{item.qty > 1 ? ` ×${item.qty}` : ""}
              </span>
            </label>
          </li>
        ))}
        {items?.length === 0 && <p className="text-sm text-slate-400">{t("order.accessories_none")}</p>}
      </ul>
      {accessoriesEnabled && (
        <div className="flex gap-2">
          <input
            type="text" value={name} onChange={(e) => setName(e.target.value)}
            placeholder={t("intake.accessory_add_placeholder")}
            className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
          />
          <button
            type="button" onClick={() => void addItem()}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch"
          >
            {t("intake.accessory_add")}
          </button>
        </div>
      )}
    </div>
  );
}
