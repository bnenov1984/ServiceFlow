/** Dashboard column 3: next actions of the selected engagement — checkbox to
 * complete, owner avatar, risk badge, collapsible completed section. */

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Avatar } from "../components/Avatar";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { NewActionDialog } from "./dialogs/NewActionDialog";
import { riskClass } from "./format";
import type { PsAssignment, PsNextAction, PsUser } from "./types";

function ownerName(users: PsUser[], userId: string): string {
  return users.find((u) => u.id === userId)?.name ?? "?";
}

export function NextActionsColumn({
  assignment,
  actions,
  users,
  isLoading,
  isError,
  errorText,
  onRetry,
}: {
  assignment: PsAssignment | null;
  actions: PsNextAction[];
  users: PsUser[];
  isLoading: boolean;
  isError: boolean;
  errorText: string;
  onRetry: () => void;
}) {
  const queryClient = useQueryClient();
  const [showCompleted, setShowCompleted] = useState(false);
  const [addOpen, setAddOpen] = useState(false);

  const forAssignment = assignment ? actions.filter((a) => a.assignment_id === assignment.id) : [];
  const open = forAssignment.filter((a) => !a.completed).sort((a, b) => a.due_on.localeCompare(b.due_on));
  const done = forAssignment.filter((a) => a.completed);
  const next = open[0] ?? null;

  const complete = async (id: string) => {
    await api.post(`/ps/next-actions/${id}/complete`);
    await queryClient.invalidateQueries({ queryKey: queryKeys.psNextActions });
  };

  const Row = ({ action }: { action: PsNextAction }) => (
    <li className="flex items-start gap-2 border-b border-slate-100 px-2 py-2 last:border-0">
      <input
        type="checkbox"
        checked={action.completed}
        disabled={action.completed}
        onChange={() => void complete(action.id)}
        aria-label={t("ps.action_mark_done")}
        className="mt-1 h-5 w-5 shrink-0"
      />
      <div className="min-w-0 flex-1">
        <p className={`font-medium ${action.completed ? "text-slate-400 line-through" : "text-slate-900"}`}>
          {action.title}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <Avatar name={ownerName(users, action.owner_user_id)} />
          <span className={`rounded-full px-2 py-0.5 font-medium ${riskClass(action.risk)}`}>
            {t(`ps.risk_${action.risk}`)}
          </span>
          <span>{action.due_on}</span>
        </div>
      </div>
    </li>
  );

  return (
    <section className="flex flex-col rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
        <h2 className="font-semibold text-slate-800">{t("ps.next_actions")}</h2>
        <button
          type="button"
          disabled={!assignment}
          onClick={() => setAddOpen(true)}
          className="shrink-0 text-sm font-medium text-blue-700 hover:underline disabled:cursor-not-allowed disabled:text-slate-300 disabled:no-underline"
        >
          {t("ps.new_action")}
        </button>
      </div>

      {!assignment ? (
        <div className="p-4">
          <EmptyState text={t("ps.actions_pick_assignment")} />
        </div>
      ) : (
        <>
          <p className="truncate px-4 pt-3 text-sm text-slate-500">
            {t("ps.actions_for", { name: assignment.title })}
          </p>
          {next && (
            <div className="mx-4 mt-2 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-blue-700">
                {t("ps.next_action_label")}
              </p>
              <div className="mt-1 flex items-center justify-between gap-2">
                <span className="min-w-0 truncate text-sm font-medium text-slate-900">{next.title}</span>
                <span className="shrink-0 text-xs text-slate-500">{next.due_on}</span>
              </div>
              <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-600">
                <Avatar name={ownerName(users, next.owner_user_id)} />
                <span>{ownerName(users, next.owner_user_id)}</span>
              </div>
            </div>
          )}
          <div className="flex-1 px-2 py-2">
            {isLoading ? (
              <div className="flex flex-col gap-2 p-2">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
              </div>
            ) : isError ? (
              <ErrorState text={errorText} onRetry={onRetry} />
            ) : open.length > 0 ? (
              <ul>{open.map((a) => <Row key={a.id} action={a} />)}</ul>
            ) : (
              <EmptyState text={t("ps.next_actions_empty")} />
            )}
          </div>
          {done.length > 0 && (
            <div className="border-t border-slate-100 px-2 py-2">
              <button
                type="button"
                onClick={() => setShowCompleted((v) => !v)}
                className="px-2 py-1 text-sm font-medium text-slate-500 hover:text-slate-700"
              >
                {showCompleted ? t("ps.hide_completed") : t("ps.show_completed", { count: done.length })}
              </button>
              {showCompleted && <ul>{done.map((a) => <Row key={a.id} action={a} />)}</ul>}
            </div>
          )}
        </>
      )}

      <NewActionDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        assignmentId={assignment?.id ?? null}
        users={users}
      />
    </section>
  );
}
