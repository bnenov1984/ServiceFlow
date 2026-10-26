/**
 * Стъпка 3 ПОРЪЧКА (docs/15 §6.4): оплакване + аксесоари + снимки (optional)
 * + части (optional, Wave 2 Issue 29) + приоритет + техник, after which the
 * submit sequence in IntakePage takes over.
 *
 * Wave 2 Issue 25: promised_on is no longer collected here — it only
 * becomes relevant once there's a diagnosis to promise against, so it moved
 * to PromisedDateBlock on the order page instead.
 */

import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { t } from "../i18n/bg";
import { TechnicianPicker } from "../components/TechnicianPicker";
import { AccessoriesChecklist } from "./AccessoriesChecklist";

// Cleanup batch Issue 26: integer, >= 0 — mirrors the backend's
// `mileage: int | None = Field(default=None, ge=0)` (OrderIn), used here
// only to decide whether Submit should be disabled for an automotive
// order; the backend (service_orders.service.create()) is still the real
// authority.
function isValidMileage(v: string): boolean {
  if (v.trim() === "") return false;
  const n = Number(v);
  return Number.isInteger(n) && n >= 0;
}

const DELIVERY_METHODS = ["pickup", "courier"] as const;
export type DeliveryMethod = (typeof DELIVERY_METHODS)[number];

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
  // Wave 5 Issue 12: "pickup" is the default/common path — the delivery
  // address only matters (and only renders) once "courier" is chosen.
  deliveryMethod: DeliveryMethod;
  deliveryAddress: string;
}

export function OrderStep({
  value,
  assetTypeCode,
  defaultDeliveryAddress,
  onChange,
  onSubmit,
  submitting,
  error,
}: {
  value: OrderStepValue;
  // Gates the mileage field (Issue 21: automotive only, never required for
  // other asset types).
  assetTypeCode: string;
  // Wave 5 Issue 12: the resolved customer's own default delivery address
  // (if any) — prefills the courier address once, never overwrites a value
  // the user already typed/edited.
  defaultDeliveryAddress: string | null;
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
  const { me } = useAuth();
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [partName, setPartName] = useState("");
  const [partPrice, setPartPrice] = useState("");

  // Cleanup batch Issue 26: required only for a vehicle asset at a company
  // whose own business_profile is "automotive_repair" — every other
  // profile/asset type keeps mileage fully optional, unchanged.
  const mileageRequired = assetTypeCode === "vehicle" && me?.business_profile === "automotive_repair";
  const mileageMissing = mileageRequired && !isValidMileage(value.mileage);

  useEffect(() => {
    if (value.deliveryMethod !== "courier") return;
    if (value.deliveryAddress.trim()) return;
    if (!defaultDeliveryAddress) return;
    onChange((prev) => ({ ...prev, deliveryAddress: defaultDeliveryAddress }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value.deliveryMethod, defaultDeliveryAddress]);

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
            {t("intake.mileage")}{mileageRequired && " *"}
          </label>
          <input
            type="number" min={0} required={mileageRequired} value={value.mileage}
            onChange={(e) => {
              const mileage = e.target.value;
              onChange((prev) => ({ ...prev, mileage }));
            }}
            className={`w-full rounded-lg border px-3 py-2 min-h-touch ${
              mileageMissing ? "border-red-600" : "border-slate-300"
            }`}
          />
          {mileageMissing && (
            <p className="mt-0.5 text-xs text-red-700">{t("errors.orders.mileage_required")}</p>
          )}
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

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">
          {t("intake.delivery_method")}
        </label>
        <div className="flex gap-2">
          {DELIVERY_METHODS.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => onChange((prev) => ({ ...prev, deliveryMethod: m }))}
              aria-pressed={value.deliveryMethod === m}
              className={`rounded-full border px-3 py-1.5 text-sm font-medium min-h-touch ${
                value.deliveryMethod === m
                  ? "border-blue-600 bg-blue-600 text-white"
                  : "border-slate-300 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {t(m === "courier" ? "intake.delivery_method_courier" : "intake.delivery_method_pickup")}
            </button>
          ))}
        </div>
        {value.deliveryMethod === "courier" && (
          <input
            type="text"
            value={value.deliveryAddress}
            onChange={(e) => {
              const deliveryAddress = e.target.value;
              onChange((prev) => ({ ...prev, deliveryAddress }));
            }}
            placeholder={t("intake.delivery_address")}
            aria-label={t("intake.delivery_address")}
            className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
        )}
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
          <TechnicianPicker
            value={value.technicianId}
            onChange={(technicianId) => onChange((prev) => ({ ...prev, technicianId }))}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
        </div>
      </div>

      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <button
        type="button"
        onClick={onSubmit}
        disabled={submitting || value.complaint.trim().length === 0 || mileageMissing}
        className="rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
      >
        {submitting ? t("common.loading") : t("intake.create_order")}
      </button>
    </div>
  );
}
