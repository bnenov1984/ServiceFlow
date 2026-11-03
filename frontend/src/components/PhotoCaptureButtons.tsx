/** Shared camera/folder capture buttons (WP-E #10, docs/15 §6.4/§6.5) — used
 * at intake (OrderStep) and on the order page (PhotosGrid). Two explicit
 * buttons instead of one generic drop-zone: the camera input carries
 * `capture="environment"` so mobile browsers open the camera directly
 * (desktop ignores the attribute and falls back to a normal file picker). */

import { useRef } from "react";
import { t } from "../i18n/bg";

export function PhotoCaptureButtons({
  onFiles,
  disabled,
  galleryAccept = "image/*",
}: {
  onFiles: (files: FileList | null) => void;
  disabled?: boolean;
  // PhotosGrid also accepts PDF documents (e.g. a repair estimate) through
  // this same "choose from device" input — the camera input stays
  // image-only regardless, since a camera can't produce a PDF.
  galleryAccept?: string;
}) {
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex gap-2">
      <button
        type="button"
        disabled={disabled}
        onClick={() => cameraRef.current?.click()}
        className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50 min-h-touch"
      >
        📷 {t("photos.take")}
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => galleryRef.current?.click()}
        className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50 min-h-touch"
      >
        📁 {t("photos.choose")}
      </button>
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => {
          onFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={galleryRef}
        type="file"
        accept={galleryAccept}
        multiple
        hidden
        onChange={(e) => {
          onFiles(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
