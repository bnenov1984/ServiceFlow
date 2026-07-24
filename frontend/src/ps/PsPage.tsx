/**
 * Professional Services — walking skeleton (trimmed first slice). One real
 * screen: clients, assignments, next actions with request-time deadline risk.
 * No Kanban/calendar/notifications — those are PS's own later, out-of-scope
 * design (module docs: modules/professional-services).
 */

import { useQueryClient, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { PsAssignment, PsClient, PsNextAction, PsStage, PsWorkflowTemplate } from "./types";

function riskClass(risk: PsNextAction["risk"]): string {
  switch (risk) {
    case "overdue":
      return "bg-red-50 text-red-700";
    case "attention":
      return "bg-amber-50 text-amber-700";
    case "done":
      return "bg-slate-100 text-slate-500";
    default:
      return "bg-green-50 text-green-700";
  }
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal");
}

export function PsPage() {
  const queryClient = useQueryClient();
  const { me } = useAuth();
  const [newClientName, setNewClientName] = useState("");
  const [newAssignmentTitle, setNewAssignmentTitle] = useState("");
  const [newAssignmentClientId, setNewAssignmentClientId] = useState("");
  const [newAssignmentTemplateId, setNewAssignmentTemplateId] = useState("");
  const [newActionTitle, setNewActionTitle] = useState("");
  const [newActionAssignmentId, setNewActionAssignmentId] = useState("");
  const [newActionDueOn, setNewActionDueOn] = useState("");
  const [stageEditAssignmentId, setStageEditAssignmentId] = useState<string | null>(null);
  const [stageEditTargetId, setStageEditTargetId] = useState("");

  const clients = useQuery({
    queryKey: queryKeys.psClients,
    queryFn: () => api.get<PsClient[]>("/ps/clients"),
  });
  const assignments = useQuery({
    queryKey: queryKeys.psAssignments,
    queryFn: () => api.get<PsAssignment[]>("/ps/assignments"),
  });
  const actions = useQuery({
    queryKey: queryKeys.psNextActions,
    queryFn: () => api.get<PsNextAction[]>("/ps/next-actions"),
  });
  const templates = useQuery({
    queryKey: queryKeys.psWorkflowTemplates,
    queryFn: () => api.get<PsWorkflowTemplate[]>("/ps/workflow-templates"),
  });
  const stageEditStages = useQuery({
    queryKey: queryKeys.psAssignmentStages(stageEditAssignmentId ?? ""),
    queryFn: () => api.get<PsStage[]>(`/ps/assignments/${stageEditAssignmentId}/stages`),
    enabled: stageEditAssignmentId !== null,
  });

  const clientName = (id: string) => clients.data?.find((c) => c.id === id)?.name ?? id;

  async function addClient() {
    if (!newClientName.trim()) return;
    await api.post("/ps/clients", { name: newClientName.trim() });
    setNewClientName("");
    await queryClient.invalidateQueries({ queryKey: queryKeys.psClients });
  }

  async function addAssignment() {
    if (!newAssignmentTitle.trim() || !newAssignmentClientId) return;
    await api.post("/ps/assignments", {
      client_id: newAssignmentClientId, title: newAssignmentTitle.trim(),
      workflow_template_id: newAssignmentTemplateId || null,
    });
    setNewAssignmentTitle("");
    setNewAssignmentTemplateId("");
    await queryClient.invalidateQueries({ queryKey: queryKeys.psAssignments });
  }

  async function addAction() {
    if (!newActionTitle.trim() || !newActionAssignmentId || !newActionDueOn || !me) return;
    await api.post("/ps/next-actions", {
      assignment_id: newActionAssignmentId, title: newActionTitle.trim(),
      owner_user_id: me.user_id, due_on: newActionDueOn,
    });
    setNewActionTitle("");
    await queryClient.invalidateQueries({ queryKey: queryKeys.psNextActions });
  }

  async function completeAction(id: string) {
    await api.post(`/ps/next-actions/${id}/complete`);
    await queryClient.invalidateQueries({ queryKey: queryKeys.psNextActions });
  }

  function openStageEdit(assignmentId: string) {
    setStageEditAssignmentId(assignmentId);
    setStageEditTargetId("");
  }

  async function submitStageChange(assignmentId: string) {
    if (!stageEditTargetId) return;
    await api.post(`/ps/assignments/${assignmentId}/stage`, { to_stage_id: stageEditTargetId });
    setStageEditAssignmentId(null);
    await queryClient.invalidateQueries({ queryKey: queryKeys.psAssignments });
  }

  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-2xl font-bold text-slate-900">{t("ps.title")}</h1>

      <section>
        <h2 className="mb-2 text-lg font-semibold text-slate-800">{t("ps.clients")}</h2>
        {clients.isLoading ? (
          <Skeleton className="h-14" />
        ) : clients.isError ? (
          <ErrorState text={errorText(clients.error)} onRetry={() => void clients.refetch()} />
        ) : clients.data && clients.data.length > 0 ? (
          <ul className="mb-3 rounded-lg border border-slate-200 bg-white">
            {clients.data.map((c) => (
              <li key={c.id} className="border-b border-slate-100 px-3 py-2 last:border-0">
                {c.name}
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState text={t("ps.clients_empty")} />
        )}
        <div className="mt-2 flex gap-2">
          <input
            value={newClientName}
            onChange={(e) => setNewClientName(e.target.value)}
            placeholder={t("ps.client_name_placeholder")}
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
          <button
            type="button"
            onClick={() => void addClient()}
            className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white min-h-touch"
          >
            {t("ps.client_add")}
          </button>
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-lg font-semibold text-slate-800">{t("ps.assignments")}</h2>
        {assignments.isLoading ? (
          <Skeleton className="h-14" />
        ) : assignments.isError ? (
          <ErrorState
            text={errorText(assignments.error)}
            onRetry={() => void assignments.refetch()}
          />
        ) : assignments.data && assignments.data.length > 0 ? (
          <ul className="mb-3 rounded-lg border border-slate-200 bg-white">
            {assignments.data.map((a) => (
              <li
                key={a.id}
                className="flex flex-col gap-2 border-b border-slate-100 px-3 py-2 last:border-0 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="font-medium text-slate-900">{a.title}</p>
                  <p className="text-sm text-slate-500">{clientName(a.client_id)}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                    {a.current_stage?.name ?? t("ps.current_stage_none")}
                  </span>
                  {stageEditAssignmentId === a.id ? (
                    <>
                      <select
                        value={stageEditTargetId}
                        onChange={(e) => setStageEditTargetId(e.target.value)}
                        className="rounded-lg border border-slate-300 px-2 py-1 text-sm min-h-touch"
                      >
                        <option value="">{t("ps.stage_change_label")}</option>
                        {stageEditStages.data?.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => void submitStageChange(a.id)}
                        className="rounded-lg border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50 min-h-touch"
                      >
                        {t("ps.stage_change_confirm")}
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      onClick={() => openStageEdit(a.id)}
                      className="rounded-lg border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50 min-h-touch"
                    >
                      {t("ps.stage_change_label")}
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState text={t("ps.assignments_empty")} />
        )}
        <div className="mt-2 flex flex-wrap gap-2">
          <select
            value={newAssignmentClientId}
            onChange={(e) => setNewAssignmentClientId(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          >
            <option value="">{t("ps.assignment_client_label")}</option>
            {clients.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            value={newAssignmentTemplateId}
            onChange={(e) => setNewAssignmentTemplateId(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          >
            <option value="">{t("ps.template_none")}</option>
            {templates.data?.map((tpl) => (
              <option key={tpl.id} value={tpl.id}>
                {tpl.name}
              </option>
            ))}
          </select>
          <input
            value={newAssignmentTitle}
            onChange={(e) => setNewAssignmentTitle(e.target.value)}
            placeholder={t("ps.assignment_title_placeholder")}
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
          <button
            type="button"
            onClick={() => void addAssignment()}
            className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white min-h-touch"
          >
            {t("ps.assignment_add")}
          </button>
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-lg font-semibold text-slate-800">{t("ps.next_actions")}</h2>
        {actions.isLoading ? (
          <Skeleton className="h-14" />
        ) : actions.isError ? (
          <ErrorState text={errorText(actions.error)} onRetry={() => void actions.refetch()} />
        ) : actions.data && actions.data.length > 0 ? (
          <ul className="mb-3 rounded-lg border border-slate-200 bg-white">
            {actions.data.map((a) => (
              <li
                key={a.id}
                className="flex items-center justify-between border-b border-slate-100 px-3 py-2 last:border-0"
              >
                <div>
                  <p className="font-medium text-slate-900">{a.title}</p>
                  <p className="text-sm text-slate-500">{a.due_on}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-medium ${riskClass(a.risk)}`}
                  >
                    {t(`ps.risk_${a.risk}`)}
                  </span>
                  {!a.completed && (
                    <button
                      type="button"
                      onClick={() => void completeAction(a.id)}
                      className="rounded-lg border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50 min-h-touch"
                    >
                      {t("ps.action_complete")}
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState text={t("ps.next_actions_empty")} />
        )}
        <div className="mt-2 flex flex-wrap gap-2">
          <select
            value={newActionAssignmentId}
            onChange={(e) => setNewActionAssignmentId(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          >
            <option value="">{t("ps.action_assignment_label")}</option>
            {assignments.data?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.title}
              </option>
            ))}
          </select>
          <input
            value={newActionTitle}
            onChange={(e) => setNewActionTitle(e.target.value)}
            placeholder={t("ps.action_title_placeholder")}
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
          <input
            type="date"
            value={newActionDueOn}
            onChange={(e) => setNewActionDueOn(e.target.value)}
            aria-label={t("ps.action_due_label")}
            className="rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
          <button
            type="button"
            onClick={() => void addAction()}
            className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white min-h-touch"
          >
            {t("ps.action_add")}
          </button>
        </div>
      </section>
    </div>
  );
}
