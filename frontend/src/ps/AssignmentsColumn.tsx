/** Dashboard column 2: engagements of the selected client — search, stage
 * filter, cards with stage/deadline/next-action badges, click to select. */

import { useEffect, useState } from "react";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { deadlineRiskClass, nextActionFor } from "./format";
import { PAGE_SIZE, PaginationFooter, paginate } from "./Pagination";
import type { PsAssignment, PsClient, PsNextAction } from "./types";

export function AssignmentsColumn({
  client,
  assignments,
  actions,
  isLoading,
  isError,
  errorText,
  onRetry,
  selectedAssignmentId,
  onSelectAssignment,
  onAddClick,
}: {
  client: PsClient | null;
  assignments: PsAssignment[];
  actions: PsNextAction[];
  isLoading: boolean;
  isError: boolean;
  errorText: string;
  onRetry: () => void;
  selectedAssignmentId: string | null;
  onSelectAssignment: (assignment: PsAssignment) => void;
  onAddClick: () => void;
}) {
  const [query, setQuery] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [page, setPage] = useState(0);

  // A page index from a previously-selected client (e.g. page 2 of a
  // client with 20 engagements) is meaningless for a different client and
  // would otherwise render an empty list if the new client has fewer
  // engagements than that page index implies.
  useEffect(() => {
    setPage(0);
  }, [client?.id]);

  const forClient = client ? assignments.filter((a) => a.client_id === client.id) : [];
  const stageOptions = [...new Map(
    forClient.filter((a) => a.current_stage).map((a) => [a.current_stage!.id, a.current_stage!.name]),
  ).entries()];
  const filtered = forClient
    .filter((a) => a.title.toLocaleLowerCase("bg").includes(query.trim().toLocaleLowerCase("bg")))
    .filter((a) => !stageFilter || a.current_stage?.id === stageFilter);
  const pageItems = paginate(filtered, page);

  return (
    <section className="flex flex-col rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
        <h2 className="min-w-0 truncate font-semibold text-slate-800">
          {client ? t("ps.assignments_for", { name: client.name }) : t("ps.assignments")}
        </h2>
        <button
          type="button"
          disabled={!client}
          onClick={onAddClick}
          className="shrink-0 text-sm font-medium text-blue-700 hover:underline disabled:cursor-not-allowed disabled:text-slate-300 disabled:no-underline"
        >
          {t("ps.new_assignment")}
        </button>
      </div>

      {!client ? (
        <div className="p-4">
          <EmptyState text={t("ps.assignments_pick_client")} />
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-2 px-4 pt-3 sm:flex-row">
            <input
              type="search"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setPage(0); }}
              placeholder={t("ps.assignment_search_placeholder")}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm min-h-touch"
            />
            <select
              value={stageFilter}
              onChange={(e) => { setStageFilter(e.target.value); setPage(0); }}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm min-h-touch"
            >
              <option value="">{t("ps.stage_filter_all")}</option>
              {stageOptions.map(([id, name]) => (
                <option key={id} value={id}>{name}</option>
              ))}
            </select>
          </div>

          <div className="flex-1 px-2 py-2">
            {isLoading ? (
              <div className="flex flex-col gap-2 p-2">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
              </div>
            ) : isError ? (
              <ErrorState text={errorText} onRetry={onRetry} />
            ) : filtered.length > 0 ? (
              <ul className="flex flex-col gap-2 p-2">
                {pageItems.map((a) => {
                  const next = nextActionFor(actions, a.id);
                  return (
                    <li key={a.id}>
                      <button
                        type="button"
                        onClick={() => onSelectAssignment(a)}
                        aria-pressed={a.id === selectedAssignmentId}
                        className={`flex w-full flex-col gap-1.5 rounded-lg border p-3 text-left ${
                          a.id === selectedAssignmentId
                            ? "border-blue-400 bg-blue-50"
                            : "border-slate-200 hover:bg-slate-50"
                        }`}
                      >
                        <p className="font-medium text-slate-900">{a.title}</p>
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                            {t("ps.current_stage_label")}
                          </span>
                          <span className="rounded-full bg-blue-600 px-2.5 py-1 text-xs font-semibold text-white">
                            {a.current_stage?.name ?? t("ps.current_stage_none")}
                          </span>
                          {a.current_stale && (
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500">
                              {t("ps.stale_badge")}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center justify-between text-xs">
                          <span className={`rounded-full px-2 py-0.5 font-medium ${deadlineRiskClass(a.current_deadline_risk)}`}>
                            {t("ps.deadline_label")}: {a.official_deadline_on ?? t("ps.deadline_none")}
                          </span>
                          {next && (
                            <span className="text-slate-500">{t("ps.next_action_label")}: {next.due_on}</span>
                          )}
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <EmptyState text={t("ps.assignments_empty")} />
            )}
          </div>
          {filtered.length > PAGE_SIZE && (
            <div className="border-t border-slate-100 px-4 py-2">
              <PaginationFooter page={page} total={filtered.length} onPageChange={setPage} />
            </div>
          )}
        </>
      )}
    </section>
  );
}
