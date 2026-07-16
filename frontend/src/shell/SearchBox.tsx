/** Header global search (docs/15 §6.8): debounced, grouped, keyboard-navigable. */

import { useQuery } from "@tanstack/react-query";
import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Highlights the matched query substring (docs/15 §6.8) — case-insensitive,
 * safe for Cyrillic since it splits on the literal query text, not word boundaries. */
function highlightMatch(text: string, query: string): ReactNode {
  if (!query.trim()) return text;
  const parts = text.split(new RegExp(`(${escapeRegExp(query.trim())})`, "gi"));
  if (parts.length === 1) return text;
  return parts.map((part, i) => (
    <Fragment key={i}>
      {part.toLowerCase() === query.trim().toLowerCase() ? <mark className="bg-amber-200 text-inherit">{part}</mark> : part}
    </Fragment>
  ));
}

interface SearchResults {
  customers: { id: string; name: string; phone: string }[];
  orders: { id: string; number: string; status_code: string; customer_name: string }[];
  assets: { id: string; label: string; customer_id: string; customer_name: string;
            matched_identifier: string }[];
}

interface FlatHit {
  key: string;
  group: string;
  label: string;
  sub: string;
  to: string;
}

function useDebounced(value: string, ms: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

export function SearchBox() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const debounced = useDebounced(query, 300);

  // "/" focuses search from anywhere outside an input (docs/10 §7).
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (e.key === "/" && !["INPUT", "TEXTAREA"].includes(target.tagName) &&
          !(target as HTMLElement).isContentEditable) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const { data, isFetching } = useQuery({
    queryKey: queryKeys.search(debounced),
    queryFn: () => api.get<SearchResults>(`/search?q=${encodeURIComponent(debounced)}`),
    enabled: debounced.trim().length >= 2,
    placeholderData: (prev) => prev,
  });

  const hits: FlatHit[] = !data
    ? []
    : [
        ...data.customers.map((c) => ({
          key: `c-${c.id}`, group: t("search.customers"), label: c.name, sub: c.phone,
          to: `/customers/${c.id}`,
        })),
        ...data.orders.map((o) => ({
          key: `o-${o.id}`, group: t("search.orders"), label: `№ ${o.number}`,
          sub: o.customer_name, to: `/orders/${o.id}`,
        })),
        ...data.assets.map((a) => ({
          key: `a-${a.id}`, group: t("search.assets"), label: a.label,
          sub: `${a.customer_name} · ${a.matched_identifier}`, to: `/customers/${a.customer_id}`,
        })),
      ];

  const go = (hit: FlatHit) => {
    setOpen(false);
    setQuery("");
    navigate(hit.to);
  };

  return (
    <div className="relative w-full max-w-md">
      <input
        ref={inputRef}
        type="search"
        role="combobox"
        aria-expanded={open && hits.length > 0}
        aria-label={t("shell.search_placeholder")}
        placeholder={t("shell.search_placeholder")}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, hits.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
          if (e.key === "Enter" && hits[active]) { e.preventDefault(); go(hits[active]); }
          if (e.key === "Escape") setOpen(false);
        }}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm min-h-touch"
      />
      {open && debounced.trim().length >= 2 && (
        <div className="absolute left-0 right-0 top-full z-40 mt-1 max-h-96 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
          {isFetching && !data ? (
            <div className="flex flex-col gap-2 p-3">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-8" />)}
            </div>
          ) : hits.length === 0 ? (
            <p className="px-4 py-3 text-sm text-slate-500">
              {t("search.empty", { q: debounced })}
            </p>
          ) : (
            hits.map((hit, index) => (
              <button
                key={hit.key}
                type="button"
                onMouseDown={(e) => { e.preventDefault(); go(hit); }}
                className={`flex w-full items-baseline justify-between gap-2 px-4 py-2 text-left text-sm ${
                  index === active ? "bg-blue-50" : "hover:bg-slate-50"
                }`}
              >
                <span>
                  <span className="mr-2 text-xs uppercase text-slate-400">{hit.group}</span>
                  <span className="font-medium text-slate-800">{highlightMatch(hit.label, debounced)}</span>
                </span>
                <span className="truncate text-slate-500">{highlightMatch(hit.sub, debounced)}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
