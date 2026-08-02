import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { Dialog } from "../../components/Dialog";
import { t } from "../../i18n/bg";
import { ApiError, api } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import type { PsNextAction, PsUser } from "../types";

export function NewActionDialog({
  open,
  onClose,
  assignmentId,
  users,
}: {
  open: boolean;
  onClose: () => void;
  assignmentId: string | null;
  users: PsUser[];
}) {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [dueOn, setDueOn] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) setOwnerId(me?.user_id ?? "");
  }, [open, me]);

  const close = () => {
    onClose();
    setTitle("");
    setDueOn("");
    setError(null);
  };

  const submit = async () => {
    if (!assignmentId || !title.trim() || !ownerId || !dueOn) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post<PsNextAction>("/ps/next-actions", {
        assignment_id: assignmentId, title: title.trim(), owner_user_id: ownerId, due_on: dueOn,
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.psNextActions });
      close();
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={close} title={t("ps.new_action_dialog_title")}>
      <div className="flex flex-col gap-3">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="new-action-title">
            {t("ps.action_title_label")}
          </label>
          <input
            id="new-action-title"
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t("ps.action_title_placeholder")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="new-action-owner">
            {t("ps.action_owner_label")}
          </label>
          <select
            id="new-action-owner"
            value={ownerId}
            onChange={(e) => setOwnerId(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          >
            {users.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="new-action-due">
            {t("ps.action_due_label")}
          </label>
          <input
            id="new-action-due"
            type="date"
            value={dueOn}
            onChange={(e) => setDueOn(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
        </div>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting || !title.trim() || !ownerId || !dueOn}
            onClick={() => void submit()}
            className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
          >
            {submitting ? t("common.loading") : t("ps.action_add")}
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
