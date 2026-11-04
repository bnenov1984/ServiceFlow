/** LaborLines (docs/15 §6.5, docs/02 §8): catalog-only lines (qty × unit_price,
 * qty fractional for an hourly catalog item — order-workflow-revamp WP-I,
 * ADR-BOS-013 §8). No free-text description/price field — see
 * CatalogItemPicker. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { CatalogItemPicker } from "./CatalogItemPicker";

interface LaborLineOut {
  id: string;
  catalog_item_id: string | null;
  description: string;
  code: string | null;
  unit: "pcs" | "hour";
  qty: number;
  unit_price: number;
}

export function LaborLinesSection({
  orderId,
  addLineBlockedHint,
}: {
  orderId: string;
  // order-workflow-revamp WP-I (Q13d) — see PartLinesSection's own prop doc.
  addLineBlockedHint: string | null;
}) {
  const queryClient = useQueryClient();
  const key = queryKeys.orderLaborLines(orderId);

  const { data: lines } = useQuery({
    queryKey: key,
    queryFn: () => api.get<LaborLineOut[]>(`/orders/${orderId}/labor-lines`),
  });

  const addLine = async (catalogItemId: string, qty: string) => {
    await api.post(`/orders/${orderId}/labor-lines`, {
      catalog_item_id: catalogItemId, qty: qty.trim() ? qty : "1",
    });
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
            {line.description}
            {line.unit === "hour" ? ` · ${line.qty} ${t("catalog.unit_hour")}` : ""}
            {" · "}{line.unit_price.toFixed(2)} €
          </li>
        ))}
        {lines?.length === 0 && <p className="text-sm text-slate-400">{t("order.labor_lines_none")}</p>}
      </ul>
      <CatalogItemPicker kind="labor" disabledHint={addLineBlockedHint} onAdd={addLine} />
    </div>
  );
}
