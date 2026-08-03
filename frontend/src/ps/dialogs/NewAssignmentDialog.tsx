import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Dialog } from "../../components/Dialog";
import { t } from "../../i18n/bg";
import { ApiError, api } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import type { PsAssignment, PsClient, PsWorkflowTemplate } from "../types";

export function NewAssignmentDialog({
  open,
  onClose,
  clients,
  templates,
  defaultClientId,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  clients: PsClient[];
  templates: PsWorkflowTemplate[];
  defaultClientId: string | null;
  onCreated: (assignment: PsAssignment) => void;
}) {
  const queryClient = useQueryClient();
  const [clientId, setClientId] = useState(defaultClientId ?? "");
  const [title, setTitle] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Re-sync when the dialog is (re)opened from a different column context.
  useEffect(() => {
    if (open) setClientId(defaultClientId ?? "");
  }, [open, defaultClientId]);

  const close = () => {
    onClose();
    setTitle("");
    setTemplateId("");
    setError(null);
  };

  const submit = async () => {
    if (!clientId || !title.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.post<PsAssignment>("/ps/assignments", {
        client_id: clientId, title: title.trim(), workflow_template_id: templateId || null,
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.psAssignments });
      onCreated(created);
      close();
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={close} title={t("ps.new_assignment_dialog_title")}>
      <div className="flex flex-col gap-3">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="new-assignment-client">
            {t("ps.assignment_client_label")}
          </label>
          <select
            id="new-assignment-client"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          >
            <option value="" />
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="new-assignment-title">
            {t("ps.assignment_title_label")}
          </label>
          <input
            id="new-assignment-title"
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t("ps.assignment_title_placeholder")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
        </div>
        {/* No workflow-template management UI exists anywhere in the app yet
            (the backend's POST /ps/workflow-templates is real but has no
            frontend caller) — every company's template list is always
            empty in practice today. Showing a picker that can only ever
            offer "no template" is worse than not showing it; this
            reappears on its own once templates actually exist. */}
        {templates.length > 0 && (
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="new-assignment-template">
              {t("ps.template_label")}
            </label>
            <select
              id="new-assignment-template"
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            >
              <option value="">{t("ps.template_none")}</option>
              {templates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>{tpl.name}</option>
              ))}
            </select>
          </div>
        )}
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting || !clientId || !title.trim()}
            onClick={() => void submit()}
            className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
          >
            {submitting ? t("common.loading") : t("ps.assignment_add")}
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
