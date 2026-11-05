/**
 * Стъпка 3 ПОРЪЧКА (docs/15 §6.4): оплакване + аксесоари + снимки (optional)
 * + приоритет + техник, after which the submit sequence in IntakePage takes
 * over.
 *
 * Wave 2 Issue 25: promised_on is no longer collected here — it only
 * becomes relevant once there's a diagnosis to promise against, so it moved
 * to PromisedDateBlock on the order page instead.
 *
 * order-workflow-revamp WP-D (Q9/Q10): mileage is optional for every
 * profile now (reverses Cleanup batch Issue 26's automotive-required
 * rule). The asset's previously recorded maximum ("floor") is fetched here
 * and shown as a hint; a value below it needs the Owner to tick a
 * confirmation box and type a comment — `service.create()`'s own check is
 * the real, authoritative guard regardless of what this UI allows through.
 *
 * order-workflow-revamp WP-I (Q13d): parts are no longer addable at intake
 * at all (reverses Wave 2 Issue 29) — a line can only be added once the
 * order has left "НОВА" (WP-G's display rename of "Приета", code still
 * `received`) (PartLinesSection/LaborLinesSection on the order page,
 * catalog-only).
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useAuth } from "../auth/AuthContext";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { PhotoCaptureButtons } from "../components/PhotoCaptureButtons";
import { TechnicianPicker } from "../components/TechnicianPicker";
import { AccessoriesChecklist } from "./AccessoriesChecklist";
import { PhotoThumbnail } from "./PhotoThumbnail";

const DELIVERY_METHODS = ["pickup", "courier"] as const;
export type DeliveryMethod = (typeof DELIVERY_METHODS)[number];

export interface OrderStepValue {
  complaint: string;
  accessories: string[];
  photos: File[];
  priority: "normal" | "high";
  technicianId: string | null;
  // Wave 3 Issues 21/26/27: only ever populated/shown for vehicle orders —
  // kept as a string like every other numeric form field here, coerced at
  // the submit boundary (IntakePage), same convention as AssetStep's number
  // fields.
  mileage: string;
  // Q10: only meaningful when `mileage` is below the asset's previous
  // maximum — Owner-only checkbox + mandatory comment, both reset whenever
  // `mileage` itself is edited again (see the mileage onChange below).
  mileageConfirmedLower: boolean;
  mileageOverrideComment: string;
  // Wave 5 Issue 12: "pickup" is the default/common path — the delivery
  // address only matters (and only renders) once "courier" is chosen.
  deliveryMethod: DeliveryMethod;
  deliveryAddress: string;
}

export function OrderStep({
  value,
  assetId,
  assetTypeCode,
  accessoriesEnabled,
  defaultDeliveryAddress,
  onChange,
  onSubmit,
  submitting,
  error,
}: {
  value: OrderStepValue;
  // Q9: the floor hint is fetched for this asset — only meaningful (and
  // only fetched) for a vehicle, see the `enabled` gate below.
  assetId: string;
  // Gates the mileage field (Issue 21: automotive only, never shown for
  // other asset types).
  assetTypeCode: string;
  // order-workflow-revamp WP-H (Q16/Q16b): gates the accessories checklist
  // below — false only for automotive's "vehicle" type.
  accessoriesEnabled: boolean;
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

  // Q9: the asset's previously recorded maximum mileage — shown as a hint,
  // and the floor a new value must not go below without the Q10 bypass.
  // Only relevant for vehicles; `current_mileage` already combines order
  // history with the legacy Asset.field_values fallback server-side.
  const { data: serviceHistory } = useQuery({
    queryKey: queryKeys.assetServiceHistory(assetId),
    queryFn: () => api.get<{ current_mileage: number | null }>(`/assets/${assetId}/service-history`),
    enabled: assetTypeCode === "vehicle",
  });
  const floor = serviceHistory?.current_mileage ?? null;
  const mileageNum = value.mileage.trim() !== "" ? Number(value.mileage) : null;
  const belowFloor = floor !== null && mileageNum !== null
    && Number.isInteger(mileageNum) && mileageNum < floor;
  const isOwner = me?.is_owner === true;
  // Q10: blocks Submit until the Owner has both ticked the box and typed a
  // comment — a non-Owner has no path through this at all.
  const mileageBlocked = belowFloor
    && !(isOwner && value.mileageConfirmedLower && value.mileageOverrideComment.trim());

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
              // Q10: a freshly edited value always needs re-confirming —
              // never let a stale checkbox/comment silently cover a new
              // number the Owner never actually looked at.
              onChange((prev) => ({
                ...prev, mileage, mileageConfirmedLower: false, mileageOverrideComment: "",
              }));
            }}
            className={`w-full rounded-lg border px-3 py-2 min-h-touch ${
              belowFloor ? "border-red-600" : "border-slate-300"
            }`}
          />
          {floor !== null && (
            <p className="mt-0.5 text-xs text-slate-400">
              {t("intake.mileage_floor_hint", { floor })}
            </p>
          )}
          {belowFloor && !isOwner && (
            <p className="mt-0.5 text-xs text-red-700">{t("intake.mileage_lower_owner_only")}</p>
          )}
          {belowFloor && isOwner && (
            <div className="mt-2 flex flex-col gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs text-amber-800">
                {t("intake.mileage_lower_warning", { floor })}
              </p>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={value.mileageConfirmedLower}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    onChange((prev) => ({ ...prev, mileageConfirmedLower: checked }));
                  }}
                />
                {t("intake.mileage_confirm_lower")}
              </label>
              {value.mileageConfirmedLower && (
                <textarea
                  required
                  rows={2}
                  value={value.mileageOverrideComment}
                  onChange={(e) => {
                    const mileageOverrideComment = e.target.value;
                    onChange((prev) => ({ ...prev, mileageOverrideComment }));
                  }}
                  placeholder={t("intake.mileage_override_comment_placeholder")}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              )}
            </div>
          )}
        </div>
      )}

      {accessoriesEnabled && (
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
      )}

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">
          {t("intake.photos")}
        </label>
        <PhotoCaptureButtons onFiles={addPhotos} />
        {value.photos.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-2">
            {value.photos.map((file, index) => (
              <li key={`${file.name}-${index}`} className="relative">
                <PhotoThumbnail file={file} />
                <button
                  type="button"
                  onClick={() => removePhoto(index)}
                  aria-label={t("common.close")}
                  className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-slate-700 text-xs text-white"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
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
        disabled={submitting || value.complaint.trim().length === 0 || mileageBlocked}
        className="rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
      >
        {submitting ? t("common.loading") : t("intake.create_order")}
      </button>
    </div>
  );
}
