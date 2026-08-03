/** Dashboard column 1 (docs/business-os task, PropertyFlow dashboard):
 * searchable client list, engagement count per client, click to select. */

import { useState } from "react";
import { Avatar } from "../components/Avatar";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { NewClientDialog } from "./dialogs/NewClientDialog";
import { PAGE_SIZE, PaginationFooter, paginate } from "./Pagination";
import type { PsAssignment, PsClient } from "./types";

function clientKindLabel(kind: string): string {
  return kind === "company" ? t("ps.client_kind_company") : t("ps.client_kind_person");
}

export function ClientsColumn({
  clients,
  assignments,
  isLoading,
  isError,
  errorText,
  onRetry,
  selectedClientId,
  onSelectClient,
}: {
  clients: PsClient[] | undefined;
  assignments: PsAssignment[] | undefined;
  isLoading: boolean;
  isError: boolean;
  errorText: string;
  onRetry: () => void;
  selectedClientId: string | null;
  onSelectClient: (client: PsClient) => void;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [addOpen, setAddOpen] = useState(false);

  const engagementCount = (clientId: string) =>
    assignments?.filter((a) => a.client_id === clientId).length ?? 0;

  const filtered = (clients ?? []).filter((c) =>
    c.name.toLocaleLowerCase("bg").includes(query.trim().toLocaleLowerCase("bg")),
  );
  const pageItems = paginate(filtered, page);

  return (
    <section className="flex flex-col rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="font-semibold text-slate-800">{t("ps.clients")}</h2>
        <button
          type="button"
          onClick={() => setAddOpen(true)}
          className="text-sm font-medium text-blue-700 hover:underline"
        >
          {t("ps.new_client")}
        </button>
      </div>
      <div className="px-4 pt-3">
        <input
          type="search"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setPage(0); }}
          placeholder={t("ps.client_search_placeholder")}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm min-h-touch"
        />
      </div>
      <div className="flex-1 px-2 py-2">
        {isLoading ? (
          <div className="flex flex-col gap-2 p-2">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
          </div>
        ) : isError ? (
          <ErrorState text={errorText} onRetry={onRetry} />
        ) : filtered.length > 0 ? (
          <ul className="flex flex-col gap-1">
            {pageItems.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => onSelectClient(c)}
                  aria-pressed={c.id === selectedClientId}
                  className={`flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left min-h-touch ${
                    c.id === selectedClientId
                      ? "border border-blue-400 bg-blue-50"
                      : "border border-transparent hover:bg-slate-50"
                  }`}
                >
                  <Avatar name={c.name} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-slate-900">{c.name}</span>
                    <span className="block text-xs text-slate-500">{clientKindLabel(c.kind)}</span>
                  </span>
                  {engagementCount(c.id) > 0 && (
                    <span
                      title={t("ps.client_order_count_label", { count: engagementCount(c.id) })}
                      aria-label={t("ps.client_order_count_label", { count: engagementCount(c.id) })}
                      className="shrink-0 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700"
                    >
                      {engagementCount(c.id)}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState text={t("ps.clients_empty")} />
        )}
      </div>
      {filtered.length > PAGE_SIZE && (
        <div className="border-t border-slate-100 px-4 py-2">
          <PaginationFooter page={page} total={filtered.length} onPageChange={setPage} />
        </div>
      )}
      <NewClientDialog open={addOpen} onClose={() => setAddOpen(false)} />
    </section>
  );
}
