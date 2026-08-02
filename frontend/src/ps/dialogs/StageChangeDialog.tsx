import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Dialog } from "../../components/Dialog";
import { t } from "../../i18n/bg";
import { ApiError, api } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import type { PsAssignment, PsStage } from "../types";

export function StageChangeDialog({
  open,
  onClose,
  assignment,
}: {
  open: boolean;
  onClose: () => void;
  assignment: PsAssignment;
}) {
  const queryClient = useQueryClient();
  const [targetId, setTargetId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const stages = useQuery({
    queryKey: queryKeys.psAssignmentStages(assignment.id),
    queryFn: () => api.get<PsStage[]>(`/ps/assignments/${assignment.id}/stages`),
    enabled: open,
  });

  const close = () => {
    onClose();
    setTargetId("");
    setError(null);
  };

  const submit = async () => {
    if (!targetId) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post<PsAssignment>(`/ps/assignments/${assignment.id}/stage`, { to_stage_id: targetId });
      await queryClient.invalidateQueries({ queryKey: queryKeys.psAssignments });
      close();
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={close} title={t("ps.stage_change_dialog_title")}>
      <div className="flex flex-col gap-3">
        <select
          autoFocus
          value={targetId}
          onChange={(e) => setTargetId(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
        >
          <option value="" />
          {stages.data?.map((s) => (
            <option key={s.id} value={s.id} disabled={s.id === assignment.current_stage?.id}>
              {s.name}
            </option>
          ))}
        </select>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting || !targetId}
            onClick={() => void submit()}
            className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
          >
            {submitting ? t("common.loading") : t("ps.stage_change_confirm")}
          </button>
          <button
            type="button"
            onClick={close}
            className="rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-50 min-h-touch"
          >
            {t("common.cancel")}
          </button>
        </div>
      </div>
    </Dialog>
  );
}
