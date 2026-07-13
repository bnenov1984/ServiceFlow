/** EmptyState / ErrorState / Skeleton — the per-screen state trio (docs/15 §6). */

import type { ReactNode } from "react";
import { t } from "../i18n/bg";

export function EmptyState({ text, action }: { text: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-slate-300 p-10 text-center">
      <p className="text-slate-500">{text}</p>
      {action}
    </div>
  );
}

export function ErrorState({ text, onRetry }: { text: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-8 text-center"
    >
      <p className="text-red-800">{text}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg bg-red-700 px-4 py-2 font-medium text-white hover:bg-red-800 min-h-touch"
        >
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded bg-slate-200 ${className}`} />;
}
