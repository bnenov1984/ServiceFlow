/** Bottom detail panel for the selected engagement: Детайли/История tabs on
 * the left, the engagement's own copied workflow stages (vertical) on the
 * right. Дата/Тип/Имот/Отговорник fields from the mockup have no backing
 * field on PSAssignment (docs/business-os task principles: show only data
 * that exists) — Детайли only lists what the API actually returns. */

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { EmptyState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { DeadlineChangeDialog } from "./dialogs/DeadlineChangeDialog";
import { StageChangeDialog } from "./dialogs/StageChangeDialog";
import type { PsAssignment, PsClient, PsDeadlineChange, PsStage } from "./types";

type Tab = "details" | "history";

function StagesPanel({ assignment, stages }: { assignment: PsAssignment; stages: PsStage[] | undefined }) {
  const currentSort = assignment.current_stage?.sort ?? -1;
  return (
    <div className="border-t border-slate-100 p-4 lg:border-l lg:border-t-0">
      <h3 className="mb-3 text-sm font-semibold text-slate-800">{t("ps.stages_panel_title")}</h3>
      {stages && stages.length > 0 ? (
        <ol className="flex flex-col gap-3">
          {[...stages].sort((a, b) => a.sort - b.sort).map((s) => {
            const state = s.sort < currentSort ? "done" : s.sort === currentSort ? "current" : "pending";
            return (
              <li key={s.id} className="flex items-center gap-2">
                <span
                  aria-hidden
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs ${
                    state === "done"
                      ? "bg-green-600 text-white"
                      : state === "current"
                        ? "bg-blue-600 text-white"
                        : "border border-slate-300 text-slate-400"
                  }`}
                >
                  {state === "done" ? "✓" : ""}
                </span>
                <span
                  className={`text-sm ${state === "pending" ? "text-slate-400" : "text-slate-800"} ${
                    state === "current" ? "font-semibold" : ""
                  }`}
                >
                  {s.name}
                </span>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="text-sm text-slate-400">{t("ps.no_workflow_stages")}</p>
      )}
    </div>
  );
}

function HistoryTab({ history, isLoading }: { history: PsDeadlineChange[] | undefined; isLoading: boolean }) {
  if (isLoading) return <Skeleton className="h-20" />;
  if (!history || history.length === 0) return <EmptyState text={t("ps.history_empty")} />;
  return (
    <ul className="flex flex-col gap-2">
      {history.map((h) => (
        <li key={h.changed_at} className="rounded-lg border border-slate-200 p-2 text-sm">
          <p className="text-slate-900">
            {h.old_value ?? t("ps.history_old_none")} → {h.new_value}
          </p>
          <p className="text-xs text-slate-500">{t("ps.history_reason_label")}: {h.reason}</p>
          <p className="text-xs text-slate-400">{new Date(h.changed_at).toLocaleString("bg-BG")}</p>
        </li>
      ))}
    </ul>
  );
}

export function AssignmentDetailPanel({
  assignment,
  client,
}: {
  assignment: PsAssignment | null;
  client: PsClient | null;
}) {
  const [tab, setTab] = useState<Tab>("details");
  const [stageOpen, setStageOpen] = useState(false);
  const [deadlineOpen, setDeadlineOpen] = useState(false);

  const stages = useQuery({
    queryKey: queryKeys.psAssignmentStages(assignment?.id ?? ""),
    queryFn: () => api.get<PsStage[]>(`/ps/assignments/${assignment?.id}/stages`),
    enabled: assignment !== null,
  });
  const history = useQuery({
    queryKey: queryKeys.psDeadlineHistory(assignment?.id ?? ""),
    queryFn: () => api.get<PsDeadlineChange[]>(`/ps/assignments/${assignment?.id}/deadline-history`),
    enabled: assignment !== null && tab === "history",
  });

  if (!assignment) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <EmptyState text={t("ps.detail_no_assignment")} />
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-slate-900">{assignment.title}</h2>
          <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
            {assignment.current_stage?.name ?? t("ps.current_stage_none")}
          </span>
        </div>
        <button
          type="button"
          disabled={stages.data?.length === 0}
          title={stages.data?.length === 0 ? t("ps.stage_change_disabled_hint") : undefined}
          onClick={() => setStageOpen(true)}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300 disabled:hover:bg-transparent min-h-touch"
        >
          {t("ps.stage_change_label")}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px]">
        <div className="p-4">
          <div role="tablist" className="mb-3 flex gap-1 border-b border-slate-100">
            {(["details", "history"] as const).map((tb) => (
              <button
                key={tb}
                type="button"
                role="tab"
                aria-selected={tab === tb}
                onClick={() => setTab(tb)}
                className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
                  tab === tb
                    ? "border-blue-600 text-blue-700"
                    : "border-transparent text-slate-500 hover:text-slate-700"
                }`}
              >
                {t(tb === "details" ? "ps.detail_tab_details" : "ps.detail_tab_history")}
              </button>
            ))}
          </div>

          {tab === "details" ? (
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs font-medium text-slate-500">{t("ps.detail_client_label")}</dt>
                <dd className="text-sm text-slate-900">{client?.name ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-slate-500">{t("ps.detail_status_label")}</dt>
                <dd className="text-sm text-slate-900">{t(`ps.lifecycle_${assignment.lifecycle_state}`)}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-slate-500">
                  {t("ps.detail_official_deadline_label")}
                </dt>
                <dd className="flex items-center gap-2 text-sm text-slate-900">
                  {assignment.official_deadline_on ?? t("ps.deadline_none")}
                  <button
                    type="button"
                    onClick={() => setDeadlineOpen(true)}
                    className="text-xs font-medium text-blue-700 hover:underline"
                  >
                    {t("ps.deadline_change_label")}
                  </button>
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-slate-500">
                  {t("ps.detail_internal_target_label")}
                </dt>
                <dd className="text-sm text-slate-900">{assignment.internal_target_on ?? "—"}</dd>
              </div>
            </dl>
          ) : (
            <HistoryTab history={history.data} isLoading={history.isLoading} />
          )}
        </div>

        <StagesPanel assignment={assignment} stages={stages.data} />
      </div>

      {/* Keyed on assignment.id: neither dialog is unmounted between engagement
          selections (this panel just re-renders with a new `assignment` prop),
          so without a fresh mount per engagement, DeadlineChangeDialog's
          `date` field - initialized once from `assignment.official_deadline_on`
          - would keep showing the *previously* selected engagement's deadline
          the first time it's reopened for a new one. */}
      <StageChangeDialog
        key={`stage-${assignment.id}`}
        open={stageOpen}
        onClose={() => setStageOpen(false)}
        assignment={assignment}
      />
      <DeadlineChangeDialog
        key={`deadline-${assignment.id}`}
        open={deadlineOpen}
        onClose={() => setDeadlineOpen(false)}
        assignment={assignment}
      />
    </section>
  );
}
