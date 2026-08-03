/** PropertyFlow settings: Owner-only create/edit of workflow templates
 * (docs/business-os PropertyFlow task). Editing a template's stages never
 * touches an assignment that already copied stages from it at creation
 * (ADR-PS-005 copy-on-create) — the backend enforces this structurally, this
 * page just calls the existing create/update contract. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { PsStageCategory, PsWorkflowTemplate } from "./types";

const STAGE_CATEGORIES: { value: PsStageCategory; labelKey: Parameters<typeof t>[0] }[] = [
  { value: "work", labelKey: "ps.stage_category_work" },
  { value: "waiting_client", labelKey: "ps.stage_category_waiting_client" },
  { value: "waiting_documents", labelKey: "ps.stage_category_waiting_documents" },
  { value: "review", labelKey: "ps.stage_category_review" },
  { value: "delivery", labelKey: "ps.stage_category_delivery" },
];

interface StageDraft {
  key: string;
  name: string;
  category: PsStageCategory;
}

let nextDraftKey = 1;
function newStageDraft(): StageDraft {
  return { key: `draft-${nextDraftKey++}`, name: "", category: "work" };
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal");
}

export function WorkflowTemplatesPage() {
  const { me } = useAuth();
  const queryClient = useQueryClient();

  const templates = useQuery({
    queryKey: queryKeys.psWorkflowTemplates,
    queryFn: () => api.get<PsWorkflowTemplate[]>("/ps/workflow-templates"),
    enabled: Boolean(me?.is_owner),
  });

  const [editingId, setEditingId] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [name, setName] = useState("");
  const [stages, setStages] = useState<StageDraft[]>([newStageDraft()]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!me?.is_owner) {
    return (
      <section>
        <ErrorState text={t("errors.auth.owner_required")} />
      </section>
    );
  }

  const openCreateForm = () => {
    setEditingId(null);
    setName("");
    setStages([newStageDraft()]);
    setError(null);
    setFormOpen(true);
  };

  const openEditForm = (template: PsWorkflowTemplate) => {
    setEditingId(template.id);
    setName(template.name);
    setStages(template.stages.map((s) => ({ key: s.id, name: s.name, category: s.category })));
    setError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setError(null);
  };

  const addStage = () => setStages((prev) => [...prev, newStageDraft()]);
  const removeStage = (key: string) => setStages((prev) => prev.filter((s) => s.key !== key));
  const moveStage = (key: string, dir: -1 | 1) => {
    setStages((prev) => {
      const index = prev.findIndex((s) => s.key === key);
      const target = index + dir;
      if (index < 0 || target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };
  const updateStageName = (key: string, value: string) =>
    setStages((prev) => prev.map((s) => (s.key === key ? { ...s, name: value } : s)));
  const updateStageCategory = (key: string, value: PsStageCategory) =>
    setStages((prev) => prev.map((s) => (s.key === key ? { ...s, category: value } : s)));

  const valid = name.trim().length > 0 && stages.length > 0
    && stages.every((s) => s.name.trim().length > 0);

  const submit = async () => {
    if (submitting || !valid) return;
    setSubmitting(true);
    setError(null);
    const body = {
      name: name.trim(),
      stages: stages.map((s) => ({ name: s.name.trim(), category: s.category })),
    };
    try {
      if (editingId) {
        await api.put<PsWorkflowTemplate>(`/ps/workflow-templates/${editingId}`, body);
      } else {
        await api.post<PsWorkflowTemplate>("/ps/workflow-templates", body);
      }
      await queryClient.invalidateQueries({ queryKey: queryKeys.psWorkflowTemplates });
      closeForm();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section>
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">{t("ps.workflow_templates_title")}</h1>
        <Link to="/ps" className="text-sm text-blue-700 hover:underline">← {t("ps.title")}</Link>
      </div>
      <p className="mb-4 text-sm text-slate-500">{t("ps.workflow_templates_subtitle")}</p>

      {!formOpen && (
        <button
          type="button"
          onClick={openCreateForm}
          className="mb-4 rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 min-h-touch"
        >
          {t("ps.template_create_action")}
        </button>
      )}

      {formOpen && (
        <div className="mb-6 flex max-w-xl flex-col gap-4 rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="font-semibold text-slate-900">
            {editingId ? t("ps.template_form_title_edit") : t("ps.template_form_title_new")}
          </h2>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="template-name">
              {t("ps.template_name_label")}
            </label>
            <input
              id="template-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("ps.template_name_placeholder")}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
          </div>

          <div>
            <p className="mb-1 text-sm font-medium text-slate-700">{t("ps.template_stages_label")}</p>
            <ul className="flex flex-col gap-2">
              {stages.map((s, i) => (
                <li key={s.key} className="flex items-center gap-2">
                  <input
                    value={s.name}
                    onChange={(e) => updateStageName(s.key, e.target.value)}
                    placeholder={t("ps.template_stage_name_placeholder")}
                    aria-label={t("ps.template_stage_name_placeholder")}
                    className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
                  />
                  <select
                    value={s.category}
                    onChange={(e) => updateStageCategory(s.key, e.target.value as PsStageCategory)}
                    aria-label={t("ps.template_stage_category_label")}
                    className="rounded-lg border border-slate-300 px-2 py-2 text-sm min-h-touch"
                  >
                    {STAGE_CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>{t(c.labelKey)}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={i === 0}
                    onClick={() => moveStage(s.key, -1)}
                    aria-label={t("ps.template_move_stage_up")}
                    className="rounded-lg border border-slate-300 px-2 py-2 text-slate-600 hover:bg-slate-50 disabled:opacity-30 min-h-touch min-w-touch"
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    disabled={i === stages.length - 1}
                    onClick={() => moveStage(s.key, 1)}
                    aria-label={t("ps.template_move_stage_down")}
                    className="rounded-lg border border-slate-300 px-2 py-2 text-slate-600 hover:bg-slate-50 disabled:opacity-30 min-h-touch min-w-touch"
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    disabled={stages.length === 1}
                    onClick={() => removeStage(s.key)}
                    aria-label={t("ps.template_remove_stage")}
                    className="rounded-lg border border-red-300 px-2 py-2 text-red-700 hover:bg-red-50 disabled:opacity-30 min-h-touch min-w-touch"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={addStage}
              className="mt-2 text-sm font-medium text-blue-700 hover:underline"
            >
              {t("ps.template_add_stage")}
            </button>
          </div>

          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

          <div className="flex gap-2">
            <button
              type="button"
              disabled={submitting || !valid}
              onClick={() => void submit()}
              className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
            >
              {submitting ? t("common.loading") : t("ps.template_save_action")}
            </button>
            <button
              type="button"
              onClick={closeForm}
              className="rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-50 min-h-touch"
            >
              {t("ps.template_form_cancel")}
            </button>
          </div>
        </div>
      )}

      {templates.isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : templates.isError ? (
        <ErrorState text={errorText(templates.error)} onRetry={() => void templates.refetch()} />
      ) : templates.data && templates.data.length > 0 ? (
        <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {templates.data.map((tpl) => (
            <li key={tpl.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <div>
                <p className="font-medium text-slate-900">{tpl.name}</p>
                <p className="text-sm text-slate-500">
                  {tpl.stages.map((s) => s.name).join(" → ")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => openEditForm(tpl)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50 min-h-touch"
              >
                {t("ps.template_edit_action")}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState text={t("ps.workflow_templates_empty")} />
      )}
    </section>
  );
}
