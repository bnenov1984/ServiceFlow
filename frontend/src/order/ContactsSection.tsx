/** ContactsList (docs/15 §6.5/§6.7, docs/02 §10): call/email/message/visit/note,
 * editable by the author until frozen (end of day, OQ-1 default). Shared
 * between the order detail screen and the customer profile — same component,
 * a different base resource (docs/15 §6.7: "общият ContactsList компонент"). */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

interface ContactRecordOut {
  id: string;
  type: string;
  direction: string | null;
  summary: string;
  occurred_at: string;
  editable: boolean;
}

const TYPES = ["call", "email", "message", "visit", "note"] as const;
const TYPE_LABEL: Record<string, Parameters<typeof t>[0]> = {
  call: "order.contact_call",
  email: "order.contact_email",
  message: "order.contact_message",
  visit: "order.contact_visit",
  note: "order.contact_note",
};

type ContactsSectionProps = { orderId: string; customerId?: undefined }
  | { orderId?: undefined; customerId: string };

export function ContactsSection({ orderId, customerId }: ContactsSectionProps) {
  const [type, setType] = useState<(typeof TYPES)[number]>("call");
  const [direction, setDirection] = useState<"in" | "out">("out");
  const [summary, setSummary] = useState("");
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const basePath = orderId ? `/orders/${orderId}` : `/customers/${customerId!}`;
  const key = orderId ? queryKeys.orderContacts(orderId) : queryKeys.customerContacts(customerId!);

  const { data: records } = useQuery({
    queryKey: key,
    queryFn: () => api.get<ContactRecordOut[]>(`${basePath}/contact-records`),
  });

  const add = async () => {
    if (!summary.trim()) return;
    setError(null);
    try {
      await api.post(`${basePath}/contact-records`, {
        type, summary: summary.trim(), direction: type === "note" ? null : direction,
      });
      setSummary("");
      await queryClient.invalidateQueries({ queryKey: key });
    } catch {
      setError(t("errors.internal"));
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.contacts")}
      </h3>
      <ul className="mb-3 flex flex-col gap-2">
        {(records ?? []).map((r) => (
          <li key={r.id} className="text-sm">
            <span className="mr-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
              {t(TYPE_LABEL[r.type] ?? "order.contact_note")}
            </span>
            <span className="text-slate-700">{r.summary}</span>
            <span className="ml-2 text-xs text-slate-400">
              {new Date(r.occurred_at).toLocaleDateString("bg-BG")}
            </span>
          </li>
        ))}
        {records?.length === 0 && <p className="text-sm text-slate-400">{t("order.contacts_none")}</p>}
      </ul>
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap gap-2">
          {TYPES.map((tp) => (
            <button
              key={tp}
              type="button"
              onClick={() => setType(tp)}
              aria-pressed={type === tp}
              className={`rounded-full px-3 py-1 text-xs font-medium min-h-touch ${
                type === tp ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {t(TYPE_LABEL[tp])}
            </button>
          ))}
        </div>
        {type !== "note" && (
          <div className="flex gap-2">
            {(["in", "out"] as const).map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDirection(d)}
                aria-pressed={direction === d}
                className={`rounded-full border px-3 py-1 text-xs font-medium min-h-touch ${
                  direction === d ? "border-blue-600 text-blue-700" : "border-slate-300 text-slate-500"
                }`}
              >
                {t(d === "in" ? "order.direction_in" : "order.direction_out")}
              </button>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <input
            type="text" value={summary} onChange={(e) => setSummary(e.target.value)}
            placeholder={t("order.contact_summary_placeholder")}
            className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
          />
          <button
            type="button" onClick={() => void add()}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch"
          >
            {t("intake.accessory_add")}
          </button>
        </div>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      </div>
    </div>
  );
}
