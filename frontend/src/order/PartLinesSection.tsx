/** PartLines (docs/15 §6.5): per-line state selector, direct-select (not
 * cycling).
 *
 * order-workflow-revamp WP-I (Q12a/Q13d): a line is added only by picking a
 * catalog item (CatalogItemPicker) — no free-text name/price field, and only
 * while the order is in one of the allowed statuses (`addLineBlockedHint`,
 * passed in by OrderPage from the order's own status_code).
 *
 * WP-J (Q5/Q5c/Q14/Q15): three states — издадена/поръчана/монтирана — with
 * two distinct add buttons (от наличност/поръчай) instead of a single
 * "Добави", a plain on/off warranty checkbox (no more per-line months), and
 * a one-click banner suggesting a status change when the server says one
 * applies (never automatic — the user still has to confirm it). */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useToast } from "../components/Toast";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { CatalogItemPicker } from "./CatalogItemPicker";

interface PartLineOut {
  id: string;
  catalog_item_id: string | null;
  name: string;
  code: string | null;
  qty: number;
  unit_cost: number;
  unit_price: number;
  state: string;
  has_warranty: boolean;
  suggested_status?: string | null;
}

const STATES = ["issued", "ordered", "installed"] as const;
const STATE_LABEL: Record<string, Parameters<typeof t>[0]> = {
  issued: "order.part_state_issued",
  ordered: "order.part_state_ordered",
  installed: "order.part_state_installed",
};

const ADD_BUTTONS = [
  { variant: "issued", labelKey: "order.part_add_issued" as const },
  { variant: "ordered", labelKey: "order.part_add_ordered" as const },
];

const SUGGESTION_LABEL: Record<string, Parameters<typeof t>[0]> = {
  waiting_parts: "order.part_suggest_waiting_parts",
  repair: "order.part_suggest_repair",
};

export function PartLinesSection({
  orderId,
  addLineBlockedHint,
}: {
  orderId: string;
  // order-workflow-revamp WP-I (Q13d): non-null while the order's status
  // doesn't allow new lines — shown in place of the picker, never a blanket
  // hidden section (OrderPage still renders this card for its existing
  // lines; see CatalogItemPicker).
  addLineBlockedHint: string | null;
}) {
  // Q14c: on by default — the user unchecks it for the rare part added
  // without the shop's own warranty.
  const [hasWarranty, setHasWarranty] = useState(true);
  // Tracked per line-id so one row's in-flight mutation never disables or
  // otherwise affects any other row's selector.
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());
  // Q5/Q5c: a one-click nudge from the server's last add/patch response —
  // local-only UI state, never persisted, cleared on dismiss or once acted on.
  const [suggestedStatus, setSuggestedStatus] = useState<string | null>(null);
  const [suggestionPending, setSuggestionPending] = useState(false);
  const queryClient = useQueryClient();
  const pushToast = useToast();
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

  const addLine = async (catalogItemId: string, qty: string, variant: string) => {
    const added = await api.post<PartLineOut>(`/orders/${orderId}/part-lines`, {
      catalog_item_id: catalogItemId, qty: qty.trim() ? Number(qty) : 1,
      state: variant, has_warranty: hasWarranty,
    });
    setHasWarranty(true);
    setSuggestedStatus(added.suggested_status ?? null);
    await invalidate();
  };

  const changeState = async (line: PartLineOut, nextState: string) => {
    if (nextState === line.state || pendingIds.has(line.id)) return;
    setPendingIds((prev) => new Set(prev).add(line.id));
    try {
      const patched = await api.patch<PartLineOut>(`/part-lines/${line.id}`, { state: nextState });
      setSuggestedStatus(patched.suggested_status ?? null);
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

  const acceptSuggestion = async () => {
    if (suggestedStatus === null || suggestionPending) return;
    setSuggestionPending(true);
    try {
      await api.post(`/orders/${orderId}/status`, { to: suggestedStatus });
      setSuggestedStatus(null);
      await invalidate();
    } catch (err) {
      pushToast("error", err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSuggestionPending(false);
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
      {suggestedStatus !== null && SUGGESTION_LABEL[suggestedStatus] && (
        <div className="mb-3 flex items-center justify-between gap-2 rounded-lg border border-blue-200 bg-blue-50 p-2 text-sm text-blue-900">
          <span>{t(SUGGESTION_LABEL[suggestedStatus])}</span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={suggestionPending}
              onClick={() => void acceptSuggestion()}
              className="rounded-lg bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
            >
              {t("common.yes")}
            </button>
            <button
              type="button"
              onClick={() => setSuggestedStatus(null)}
              className="rounded-lg border border-blue-300 px-2 py-1 text-xs hover:bg-blue-100 min-h-touch"
            >
              {t("common.no")}
            </button>
          </div>
        </div>
      )}
      {addLineBlockedHint === null && (
        <label className="mb-2 flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={hasWarranty}
            onChange={(e) => setHasWarranty(e.target.checked)}
            className="h-4 w-4"
          />
          {t("order.part_warranty_label")}
        </label>
      )}
      <CatalogItemPicker
        kind="part" disabledHint={addLineBlockedHint} onAdd={addLine} addButtons={ADD_BUTTONS}
      />
    </div>
  );
}
