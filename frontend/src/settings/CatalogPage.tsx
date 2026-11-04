/** Catalog (Settings → Каталог, order-workflow-revamp WP-I, Q12b,
 * ADR-BOS-013): Owner-only price-list CRUD + CSV/Excel import with a
 * dry-run preview before commit. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { SettingsNav } from "./SettingsNav";

interface CatalogItemOut {
  id: string;
  kind: "part" | "labor";
  name: string;
  code: string | null;
  unit: "pcs" | "hour";
  sale_price: number;
  unit_cost: number | null;
  archived: boolean;
}

interface ImportRowOut {
  row_number: number;
  action: "insert" | "update" | "error";
  kind: string;
  name: string;
  code: string | null;
  unit: string;
  sale_price: string;
  unit_cost: string | null;
  error: string | null;
}

interface ImportResultOut {
  rows: ImportRowOut[];
  insert_count: number;
  update_count: number;
  error_count: number;
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal");
}

export function CatalogPage() {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const [includeArchived, setIncludeArchived] = useState(false);
  const key = queryKeys.catalogItems(undefined, includeArchived);

  const items = useQuery({
    queryKey: key,
    queryFn: () => api.get<CatalogItemOut[]>(
      `/catalog-items?include_archived=${includeArchived}`,
    ),
    enabled: Boolean(me?.is_owner),
  });

  const [kind, setKind] = useState<"part" | "labor">("part");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [unit, setUnit] = useState<"pcs" | "hour">("pcs");
  const [salePrice, setSalePrice] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [patchError, setPatchError] = useState<string | null>(null);
  const [patchingId, setPatchingId] = useState<string | null>(null);

  const [importResult, setImportResult] = useState<ImportResultOut | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  if (!me?.is_owner) {
    return (
      <section>
        <SettingsNav />
        <ErrorState text={t("catalog.access_denied")} />
      </section>
    );
  }

  const invalidateAll = async () => {
    await queryClient.invalidateQueries({ queryKey: ["catalog-items"] });
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting || !name.trim()) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await api.post("/catalog-items", {
        kind, name: name.trim(), unit,
        sale_price: salePrice.trim() ? Number(salePrice) : 0,
        code: code.trim() || undefined,
        unit_cost: unitCost.trim() ? Number(unitCost) : undefined,
      });
      setName(""); setCode(""); setSalePrice(""); setUnitCost(""); setUnit("pcs");
      await invalidateAll();
    } catch (err) {
      setFormError(errorText(err));
    } finally {
      setSubmitting(false);
    }
  };

  const toggleArchive = async (item: CatalogItemOut) => {
    if (patchingId) return;
    setPatchingId(item.id);
    setPatchError(null);
    try {
      await api.post(`/catalog-items/${item.id}/${item.archived ? "unarchive" : "archive"}`);
      await invalidateAll();
    } catch (err) {
      setPatchError(errorText(err));
    } finally {
      setPatchingId(null);
    }
  };

  const runImport = async (mode: "preview" | "commit") => {
    const file = fileInputRef.current?.files?.[0];
    if (!file || importBusy) return;
    setImportBusy(true);
    setImportError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await api.post<ImportResultOut>(`/catalog-items/import/${mode}`, form);
      setImportResult(result);
      if (mode === "commit") {
        await invalidateAll();
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    } catch (err) {
      setImportError(errorText(err));
    } finally {
      setImportBusy(false);
    }
  };

  return (
    <section>
      <SettingsNav />
      <h1 className="mb-4 text-xl font-semibold text-slate-900">{t("catalog.title")}</h1>

      <form
        onSubmit={(e) => void onSubmit(e)}
        className="mb-6 flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
      >
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-700" htmlFor="catalog-field-kind">
            {t("catalog.field_kind")}
          </label>
          <select
            id="catalog-field-kind"
            value={kind}
            onChange={(e) => setKind(e.target.value as "part" | "labor")}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
          >
            <option value="part">{t("catalog.kind_part")}</option>
            <option value="labor">{t("catalog.kind_labor")}</option>
          </select>
        </div>
        <div className="min-w-[10rem] flex-1">
          <label className="mb-1 block text-xs font-medium text-slate-700" htmlFor="catalog-field-name">
            {t("catalog.field_name")}
          </label>
          <input
            id="catalog-field-name"
            value={name} onChange={(e) => setName(e.target.value)} required
            className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-700" htmlFor="catalog-field-code">
            {t("catalog.field_code")}
          </label>
          <input
            id="catalog-field-code"
            value={code} onChange={(e) => setCode(e.target.value)}
            className="w-28 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
          />
        </div>
        {kind === "labor" && (
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700" htmlFor="catalog-field-unit">
              {t("catalog.field_unit")}
            </label>
            <select
              id="catalog-field-unit"
              value={unit}
              onChange={(e) => setUnit(e.target.value as "pcs" | "hour")}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
            >
              <option value="pcs">{t("catalog.unit_pcs")}</option>
              <option value="hour">{t("catalog.unit_hour")}</option>
            </select>
          </div>
        )}
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-700" htmlFor="catalog-field-sale-price">
            {t("catalog.field_sale_price")}
          </label>
          <input
            id="catalog-field-sale-price"
            type="number" min={0} step="0.01" value={salePrice}
            onChange={(e) => setSalePrice(e.target.value)}
            className="w-24 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-700" htmlFor="catalog-field-unit-cost">
            {t("catalog.field_unit_cost")}
          </label>
          <input
            id="catalog-field-unit-cost"
            type="number" min={0} step="0.01" value={unitCost}
            onChange={(e) => setUnitCost(e.target.value)}
            className="w-24 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
          />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
        >
          {submitting ? t("common.loading") : t("catalog.add_action")}
        </button>
        {formError && <p role="alert" className="w-full text-sm text-red-700">{formError}</p>}
      </form>

      <label className="mb-2 flex items-center gap-2 text-sm text-slate-600">
        <input
          type="checkbox" checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
        />
        {t("catalog.show_archived")}
      </label>

      {items.isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : items.isError ? (
        <ErrorState text={errorText(items.error)} onRetry={() => void items.refetch()} />
      ) : items.data && items.data.length > 0 ? (
        <ul className="mb-8 divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {items.data.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <div>
                <p className="font-medium text-slate-900">
                  {item.name}
                  {item.code && <span className="ml-2 text-xs text-slate-400">#{item.code}</span>}
                </p>
                <p className="text-sm text-slate-500">
                  {t(item.kind === "part" ? "catalog.kind_part" : "catalog.kind_labor")}
                  {" · "}{item.sale_price.toFixed(2)} € / {t(
                    item.unit === "hour" ? "catalog.unit_hour" : "catalog.unit_pcs",
                  )}
                  {item.unit_cost !== null && (
                    <> {" · "}{t("catalog.field_unit_cost")}: {item.unit_cost.toFixed(2)} €</>
                  )}
                </p>
              </div>
              <div className="flex items-center gap-3 text-sm">
                {item.archived && (
                  <span className="text-slate-400">{t("catalog.archived_label")}</span>
                )}
                <button
                  type="button"
                  disabled={patchingId === item.id}
                  onClick={() => void toggleArchive(item)}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 min-h-touch"
                >
                  {item.archived ? t("catalog.unarchive_action") : t("catalog.archive_action")}
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mb-8 text-sm text-slate-400">{t("catalog.empty")}</p>
      )}
      {patchError && <p role="alert" className="mb-8 text-sm text-red-700">{patchError}</p>}

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          {t("catalog.import_title")}
        </h2>
        <p className="mb-3 text-sm text-slate-500">{t("catalog.import_hint")}</p>
        <div className="flex flex-wrap items-center gap-2">
          <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xlsm" className="text-sm" />
          <button
            type="button"
            disabled={importBusy}
            onClick={() => void runImport("preview")}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50 min-h-touch"
          >
            {t("catalog.import_preview_action")}
          </button>
          {importResult && importResult.error_count === 0 && (
            <button
              type="button"
              disabled={importBusy}
              onClick={() => void runImport("commit")}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
            >
              {t("catalog.import_commit_action")}
            </button>
          )}
        </div>
        {importError && <p role="alert" className="mt-2 text-sm text-red-700">{importError}</p>}
        {importResult && (
          <div className="mt-3">
            <p className="mb-2 text-sm text-slate-600">
              {t("catalog.import_summary", {
                insert: importResult.insert_count, update: importResult.update_count,
                errors: importResult.error_count,
              })}
            </p>
            <ul className="flex max-h-64 flex-col gap-1 overflow-y-auto text-xs">
              {importResult.rows.map((row) => (
                <li
                  key={row.row_number}
                  className={row.action === "error" ? "text-red-700" : "text-slate-600"}
                >
                  #{row.row_number} {row.name || "—"} — {row.action === "error"
                    ? (row.error ? t(row.error) : t("errors.internal"))
                    : t(row.action === "insert" ? "catalog.import_row_insert" : "catalog.import_row_update")}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
