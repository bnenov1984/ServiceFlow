/** PhotosGrid (docs/15 §6.5, docs/02 §9): stage tabs, upload, lightbox. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Dialog } from "../components/Dialog";
import { PhotoCaptureButtons } from "../components/PhotoCaptureButtons";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { apiUrl } from "../lib/apiUrl";
import { queryKeys } from "../lib/queryKeys";

interface AttachmentOut {
  id: string;
  kind: "photo" | "document";
  stage: string;
  caption: string;
  mime: string;
  has_thumbnail: boolean;
  display_name: string;
}

const STAGES = ["all", "reception", "progress", "completed", "other"] as const;
const STAGE_LABEL: Record<string, Parameters<typeof t>[0]> = {
  all: "order.stage_all",
  reception: "order.stage_reception",
  progress: "order.stage_progress",
  completed: "order.stage_completed",
  other: "order.stage_other",
};

export function PhotosGrid({ orderId }: { orderId: string }) {
  const [activeStage, setActiveStage] = useState<(typeof STAGES)[number]>("all");
  const [lightboxId, setLightboxId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const queryClient = useQueryClient();
  const key = queryKeys.orderAttachments(orderId);

  const { data: attachments } = useQuery({
    queryKey: key,
    queryFn: () => api.get<AttachmentOut[]>(`/orders/${orderId}/attachments`),
  });

  const shown = (attachments ?? []).filter((a) => activeStage === "all" || a.stage === activeStage);

  const upload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("file", file);
        form.append("stage", activeStage === "all" ? "other" : activeStage);
        await api.post(`/orders/${orderId}/attachments`, form);
      }
      await queryClient.invalidateQueries({ queryKey: key });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.photos")}
      </h3>
      <div className="mb-2 flex flex-wrap gap-1">
        {STAGES.map((stage) => (
          <button
            key={stage}
            type="button"
            onClick={() => setActiveStage(stage)}
            aria-pressed={activeStage === stage}
            className={`rounded-full px-3 py-1 text-xs font-medium min-h-touch ${
              activeStage === stage ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {t(STAGE_LABEL[stage])}
          </button>
        ))}
      </div>

      <div className="mb-3 grid grid-cols-3 gap-2 sm:grid-cols-4">
        {shown.map((a) => (
          <button
            key={a.id}
            type="button"
            onClick={() => setLightboxId(a.id)}
            className="aspect-square overflow-hidden rounded-lg border border-slate-200 bg-slate-50"
          >
            {a.kind === "photo" ? (
              <img
                src={apiUrl(`/api/v1/attachments/${a.id}/file?thumb=true`)}
                alt={a.caption || t("order.photos")}
                className="h-full w-full object-cover"
              />
            ) : (
              <span className="flex h-full items-center justify-center text-xs text-slate-400">PDF</span>
            )}
          </button>
        ))}
        {shown.length === 0 && (
          <p className="col-span-full text-sm text-slate-400">{t("order.photos_none")}</p>
        )}
      </div>

      {uploading ? (
        <p className="text-sm text-slate-500">{t("common.loading")}</p>
      ) : (
        <PhotoCaptureButtons
          onFiles={(files) => void upload(files)}
          disabled={uploading}
          galleryAccept="image/*,application/pdf"
        />
      )}

      <Dialog open={lightboxId !== null} onClose={() => setLightboxId(null)} title={t("order.photos")}>
        {lightboxId && (
          <>
            <img
              src={apiUrl(`/api/v1/attachments/${lightboxId}/file`)}
              alt=""
              className="max-h-[70vh] w-full object-contain"
            />
            <p className="mt-2 text-center text-xs text-slate-500">
              {shown.find((a) => a.id === lightboxId)?.display_name}
            </p>
          </>
        )}
      </Dialog>
    </div>
  );
}
