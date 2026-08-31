/**
 * Стъпка 3 ПОРЪЧКА (docs/15 §6.4): оплакване + аксесоари + снимки (optional)
 * + части (optional, Wave 2 Issue 29) + приоритет + техник, after which the
 * submit sequence in IntakePage takes over.
 *
 * Wave 2 Issue 25: promised_on is no longer collected here — it only
 * becomes relevant once there's a diagnosis to promise against, so it moved
 * to PromisedDateBlock on the order page instead.
 */

import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { AccessoriesChecklist } from "./AccessoriesChecklist";

export interface PartLineDraft {
  name: string;
  unitPrice: number;
}

export interface OrderStepValue {
  complaint: string;
  accessories: string[];
  photos: File[];
  partLines: PartLineDraft[];
  priority: "normal" | "high";
  technicianId: string | null;
  // Wave 3 Issues 21/26/27: only ever populated/shown for vehicle orders —
  // kept as a string like every other numeric form field here, coerced at
  // the submit boundary (IntakePage), same convention as AssetStep's number
  // fields.
  mileage: string;
}

interface UserOut {
  id: string;
  name: string;
  is_owner: boolean;
  is_active: boolean;
}

export function OrderStep({
  value,
  assetTypeCode,
  onChange,
  onSubmit,
  submitting,
  error,
}: {
  value: OrderStepValue;
  // Gates the mileage field (Issue 21: automotive only, never required for
  // other asset types).
  assetTypeCode: string;
  // Updater-only (never a raw next-value): every mutation computes its result
  // from `prev` at apply-time, so React can chain multiple same-batch updates
  // correctly regardless of dispatch order (see AccessoriesChecklist for the
  // bug this closes — this is React's own functional-setState guarantee,
  // deliberately the ONLY form accepted here so it can't regress).
  onChange: (updater: (prev: OrderStepValue) => OrderStepValue) => void;
  onSubmit: () => void;
  submitting: boolean;
  error: string | null;
}) {
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [partName, setPartName] = useState("");
  const [partPrice, setPartPrice] = useState("");

  const { data: users } = useQuery({
    queryKey: queryKeys.users,
    queryFn: () => api.get<UserOut[]>("/users"),
  });

  const addPhotos = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const added = Array.from(files);
    onChange((prev) => ({ ...prev, photos: [...prev.photos, ...added] }));
  };

  const removePhoto = (index: number) => {
    onChange((prev) => ({ ...prev, photos: prev.photos.filter((_, i) => i !== index) }));
  };

  // Issue 29: a part can be added already at intake, reusing the same
  // draft-list-then-best-effort-POST pattern accessories/photos already use
  // (IntakePage's submit sequence) — no new part-line shape, no inventory.
  const addPartLine = () => {
    if (!partName.trim()) return;
    const unitPrice = partPrice.trim() ? Number(partPrice) : 0;
    onChange((prev) => ({
      ...prev, partLines: [...prev.partLines, { name: partName.trim(), unitPrice }],
    }));
    setPartName("");
    setPartPrice("");
  };

  const removePartLine = (index: number) => {
    onChange((prev) => ({ ...prev, partLines: prev.partLines.filter((_, i) => i !== index) }));
  };

  return (
    <div className="flex flex-col gap-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">
          {t("intake.complaint")}
        </label>
        <textarea
          required
          autoFocus
          rows={3}
          value={value.complaint}
          onChange={(e) => {
            const complaint = e.target.value;
            onChange((prev) => ({ ...prev, complaint }));
          }}
          className="w-full rounded-lg border border-slate-300 px-3 py-2"
        />
      </div>

      {assetTypeCode === "vehicle" && (
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            {t("intake.mileage")}
          </label>
          <input
            type="number" min={0} value={value.mileage}
            onChange={(e) => {
              const mileage = e.target.value;
              onChange((prev) => ({ ...prev, mileage }));
            }}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
        </div>
      )}

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">
          {t("intake.accessories")}
        </label>
        <AccessoriesChecklist
          selected={value.accessories}
          onToggle={(name) =>
            onChange((prev) => ({
              ...prev,
              accessories: prev.accessories.includes(name)
                ? prev.accessories.filter((a) => a !== name)
                : [...prev.accessories, name],
            }))
          }
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">
          {t("intake.photos")}
        </label>
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); addPhotos(e.dataTransfer.files); }}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer rounded-lg border-2 border-dashed p-4 text-center text-sm ${
            dragOver ? "border-blue-400 bg-blue-50" : "border-slate-300 text-slate-500"
          }`}
        >
          {t("intake.photos_drop_hint")}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            hidden
            onChange={(e) => addPhotos(e.target.files)}
          />
        </div>
        {value.photos.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-2">
            {value.photos.map((file, index) => (
              <li key={`${file.name}-${index}`} className="flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-xs">
                {file.name}
                <button type="button" onClick={() => removePhoto(index)} aria-label={t("common.close")}>
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">
          {t("intake.parts")}
        </label>
        {value.partLines.length > 0 ? (
          <ul className="mb-2 flex flex-col gap-1">
            {value.partLines.map((line, index) => (
              <li key={`${line.name}-${index}`} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-1.5 text-sm">
                <span>{line.name} · {line.unitPrice.toFixed(2)} €</span>
                <button type="button" onClick={() => removePartLine(index)} aria-label={t("common.close")}>
                  ✕
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mb-2 text-sm text-slate-400">{t("intake.parts_none")}</p>
        )}
        <div className="flex gap-2">
          <input
            type="text" value={partName} onChange={(e) => setPartName(e.target.value)}
            placeholder={t("order.part_name_placeholder")}
            className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
          />
          <input
            type="number" min={0} step="0.01" value={partPrice}
            onChange={(e) => setPartPrice(e.target.value)}
            placeholder="€" className="w-20 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
          />
          <button
            type="button" onClick={addPartLine}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch"
          >
            {t("intake.accessory_add")}
          </button>
        </div>
      </div>

      <div className="flex gap-6">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            {t("intake.priority")}
          </label>
          <div className="flex gap-2">
            {(["normal", "high"] as const).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => onChange((prev) => ({ ...prev, priority: p }))}
                aria-pressed={value.priority === p}
                className={`rounded-full border px-3 py-1.5 text-sm font-medium min-h-touch ${
                  value.priority === p
                    ? "border-priority-high bg-priority-high text-white"
                    : "border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {t(p === "high" ? "intake.priority_high" : "intake.priority_normal")}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium text-slate-700">
            {t("intake.technician")}
          </label>
          <select
            value={value.technicianId ?? ""}
            onChange={(e) => {
              const technicianId = e.target.value || null;
              onChange((prev) => ({ ...prev, technicianId }));
            }}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          >
            <option value="">{t("intake.technician_unassigned")}</option>
            {(users ?? []).filter((u) => u.is_active).map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        </div>
      </div>

      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <button
        type="button"
        onClick={onSubmit}
        disabled={submitting || value.complaint.trim().length === 0}
        className="rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
      >
        {submitting ? t("common.loading") : t("intake.create_order")}
      </button>
    </div>
  );
}
