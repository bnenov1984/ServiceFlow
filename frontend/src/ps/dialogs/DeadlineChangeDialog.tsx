import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Dialog } from "../../components/Dialog";
import { t } from "../../i18n/bg";
import { ApiError, api } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import type { PsAssignment } from "../types";

export function DeadlineChangeDialog({
  open,
  onClose,
  assignment,
}: {
  open: boolean;
  onClose: () => void;
  assignment: PsAssignment;
}) {
  const queryClient = useQueryClient();
  const [date, setDate] = useState(assignment.official_deadline_on ?? "");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const close = () => {
    onClose();
    setReason("");
    setError(null);
  };

  const submit = async () => {
    if (!date || !reason.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post<PsAssignment>(`/ps/assignments/${assignment.id}/deadline`, {
        official_deadline_on: date, reason: reason.trim(),
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.psAssignments });
      await queryClient.invalidateQueries({ queryKey: queryKeys.psDeadlineHistory(assignment.id) });
      close();
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={close} title={t("ps.deadline_change_dialog_title")}>
      <div className="flex flex-col gap-3">
        <input
          autoFocus
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
        />
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={t("ps.deadline_reason_placeholder")}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
        />
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting || !date || !reason.trim()}
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
