/** Client-side pagination footer shared by the three dashboard columns — the
 * list endpoints (docs/business-os) return everything, no server paging. */

import { t } from "../i18n/bg";

export const PAGE_SIZE = 8;

export function paginate<T>(items: T[], page: number, pageSize: number = PAGE_SIZE): T[] {
  return items.slice(page * pageSize, (page + 1) * pageSize);
}

export function PaginationFooter({
  page,
  pageSize = PAGE_SIZE,
  total,
  onPageChange,
}: {
  page: number;
  pageSize?: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  if (total === 0) return null;
  const from = page * pageSize + 1;
  const to = Math.min(total, (page + 1) * pageSize);

  return (
    <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
      <span>{t("ps.pagination_showing", { from, to, total })}</span>
      <div className="flex gap-1">
        <button
          type="button"
          disabled={page <= 0}
          aria-label={t("ps.pagination_prev")}
          onClick={() => onPageChange(page - 1)}
          className="rounded border border-slate-300 px-2 py-1 disabled:opacity-40 min-h-touch min-w-touch"
        >
          ‹
        </button>
        <button
          type="button"
          disabled={to >= total}
          aria-label={t("ps.pagination_next")}
          onClick={() => onPageChange(page + 1)}
          className="rounded border border-slate-300 px-2 py-1 disabled:opacity-40 min-h-touch min-w-touch"
        >
          ›
        </button>
      </div>
    </div>
  );
}
