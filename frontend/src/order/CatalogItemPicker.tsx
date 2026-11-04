/** order-workflow-revamp WP-I (Q12a/Q12e, ADR-BOS-013): the only way a
 * part/labor line is added — pick a catalog item, no free-text name or
 * price field anywhere. Shared by PartLinesSection and LaborLinesSection
 * (identical picker + qty + inline "Добави в каталога" shortcut; only the
 * `kind` and the resulting line endpoint differ, which the caller owns).
 *
 * WP-J (Q15b): PartLinesSection needs two distinct add buttons ("От
 * наличност"/"Поръчай", picking the new line's initial state) instead of
 * one — `addButtons` lets a caller offer that without forking this
 * component; LaborLinesSection doesn't pass it and keeps the single default
 * button exactly as before. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export interface CatalogItemOut {
  id: string;
  kind: "part" | "labor";
  name: string;
  code: string | null;
  unit: "pcs" | "hour";
  sale_price: number;
  unit_cost: number | null;
  archived: boolean;
}

export interface AddButton {
  variant: string;
  labelKey: Parameters<typeof t>[0];
}

const DEFAULT_ADD_BUTTONS: AddButton[] = [{ variant: "default", labelKey: "intake.accessory_add" }];

export function CatalogItemPicker({
  kind,
  disabledHint,
  onAdd,
  addButtons = DEFAULT_ADD_BUTTONS,
}: {
  kind: "part" | "labor";
  // When set, the whole add-form is replaced with this explanatory text
  // instead (Q13d: lines are only addable in certain statuses) — never a
  // silent disabled control with no explanation.
  disabledHint: string | null;
  onAdd: (catalogItemId: string, qty: string, variant: string) => Promise<void>;
  // WP-J (Q15b): one button per entry, each submitting with its own
  // `variant` string — defaults to the single "Добави" button every other
  // caller (LaborLinesSection) already expects.
  addButtons?: AddButton[];
}) {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const key = queryKeys.catalogItems(kind);
  const { data: items } = useQuery({
    queryKey: key,
    queryFn: () => api.get<CatalogItemOut[]>(`/catalog-items?kind=${kind}`),
  });

  const [selectedId, setSelectedId] = useState("");
  const [qty, setQty] = useState("1");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [quickAddName, setQuickAddName] = useState("");
  const [quickAddPrice, setQuickAddPrice] = useState("");
  const [quickAddUnit, setQuickAddUnit] = useState<"pcs" | "hour">("pcs");
  const [quickAddSubmitting, setQuickAddSubmitting] = useState(false);
  const [quickAddError, setQuickAddError] = useState<string | null>(null);

  const selected = (items ?? []).find((i) => i.id === selectedId) ?? null;
  const isHourly = kind === "labor" && selected?.unit === "hour";

  if (disabledHint !== null) {
    return <p className="text-sm text-slate-400">{disabledHint}</p>;
  }

  const addLine = async (variant: string) => {
    if (!selectedId || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await onAdd(selectedId, qty, variant);
      setSelectedId("");
      setQty("1");
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  const submitQuickAdd = async () => {
    if (!quickAddName.trim() || quickAddSubmitting) return;
    setQuickAddSubmitting(true);
    setQuickAddError(null);
    try {
      const created = await api.post<CatalogItemOut>("/catalog-items", {
        kind, name: quickAddName.trim(), unit: quickAddUnit,
        sale_price: quickAddPrice.trim() ? Number(quickAddPrice) : 0,
      });
      await queryClient.invalidateQueries({ queryKey: key });
      setSelectedId(created.id);
      setQuickAddOpen(false);
      setQuickAddName("");
      setQuickAddPrice("");
      setQuickAddUnit("pcs");
    } catch (err) {
      setQuickAddError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setQuickAddSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <select
          value={selectedId}
          onChange={(e) => {
            setSelectedId(e.target.value);
            setQty("1");
          }}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
        >
          <option value="">{t("catalog.picker_placeholder")}</option>
          {(items ?? []).map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} · {item.sale_price.toFixed(2)} € / {t(
                item.unit === "hour" ? "catalog.unit_hour" : "catalog.unit_pcs",
              )}
            </option>
          ))}
        </select>
        <input
          type="number"
          min={isHourly ? 0.25 : 1}
          step={isHourly ? "0.25" : "1"}
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          aria-label={t("catalog.qty_label")}
          className="w-20 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
        />
        {addButtons.map((b) => (
          <button
            key={b.variant}
            type="button"
            disabled={!selectedId || submitting}
            onClick={() => void addLine(b.variant)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50 min-h-touch"
          >
            {t(b.labelKey)}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
      {items?.length === 0 && (
        <p className="text-xs text-slate-400">{t("catalog.picker_empty")}</p>
      )}

      {me?.is_owner && (
        quickAddOpen ? (
          <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2">
            <div className="flex gap-2">
              <input
                type="text"
                value={quickAddName}
                onChange={(e) => setQuickAddName(e.target.value)}
                placeholder={t("catalog.quick_add_name_placeholder")}
                className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
              />
              <input
                type="number"
                min={0}
                step="0.01"
                value={quickAddPrice}
                onChange={(e) => setQuickAddPrice(e.target.value)}
                placeholder="€"
                className="w-24 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
              />
              {kind === "labor" && (
                <select
                  value={quickAddUnit}
                  onChange={(e) => setQuickAddUnit(e.target.value as "pcs" | "hour")}
                  className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm min-h-touch"
                >
                  <option value="pcs">{t("catalog.unit_pcs")}</option>
                  <option value="hour">{t("catalog.unit_hour")}</option>
                </select>
              )}
            </div>
            {quickAddError && <p role="alert" className="text-xs text-red-700">{quickAddError}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                disabled={quickAddSubmitting}
                onClick={() => void submitQuickAdd()}
                className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
              >
                {t("catalog.quick_add_submit")}
              </button>
              <button
                type="button"
                onClick={() => setQuickAddOpen(false)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50 min-h-touch"
              >
                {t("common.cancel")}
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setQuickAddOpen(true)}
            className="self-start text-xs font-medium text-blue-700 hover:underline"
          >
            {t("catalog.add_new_item_prompt")}
          </button>
        )
      )}
    </div>
  );
}
