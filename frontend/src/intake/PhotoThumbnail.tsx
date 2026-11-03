/** Client-side preview for a not-yet-uploaded intake photo (WP-E #12) — the
 * file only reaches the server after the order is created (IntakePage's
 * best-effort-POST sequence), so this is the only preview available at
 * intake time, built from the File object itself via an object URL. */

import { useEffect, useState } from "react";
import { t } from "../i18n/bg";

export function PhotoThumbnail({ file }: { file: File }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  if (!url) return null;
  return (
    <img
      src={url}
      alt={file.name || t("intake.photos")}
      className="h-16 w-16 rounded-lg border border-slate-200 object-cover"
    />
  );
}
