/** TimelineSection (docs/15 §6.5, BR-5): read-only, newest first, actor + time.
 * Users never edit history (docs/01 §TimelineEvent).
 *
 * Wave 2 Issue 34: order-scoped communication (call/email/note, plus any
 * historical message/visit record) has no separate ContactsSection on the
 * order page any more — note_or_contact_recorded events render their actual
 * content (type badge + summary) here instead of a generic label, the same
 * content ContactsSection used to show in its own list. */

import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { t } from "../i18n/bg";
import { TYPE_LABEL as CONTACT_TYPE_LABEL } from "./ContactsSection";

interface TimelineEventOut {
  event_type: string;
  actor_user_id: string | null;
  data: Record<string, unknown>;
  created_at: string;
}

interface UserOut {
  id: string;
  name: string;
}

// Event-type -> message key (docs/01 §5 catalog). Params are filled from `data`
// where present; the fallback shows the raw type so nothing silently disappears.
const EVENT_LABEL: Record<string, Parameters<typeof t>[0]> = {
  order_created: "order.event_created",
  status_changed: "order.event_status_changed",
  technician_assigned: "order.event_technician_assigned",
  diagnosis_recorded: "order.event_diagnosis_recorded",
  diagnosis_updated: "order.event_diagnosis_updated",
  estimate_approved: "order.event_estimate_approved",
  estimate_rejected: "order.event_estimate_rejected",
  order_unlocked: "order.event_unlocked",
  order_delivered: "order.event_delivered",
  order_archived: "order.event_archived",
  warranty_return_opened: "order.event_warranty_return",
  task_created: "order.event_task_created",
  task_completed: "order.event_task_completed",
  part_added: "order.event_part_added",
  part_state_changed: "order.event_part_state_changed",
  labor_added: "order.event_labor_added",
  accessory_added: "order.event_accessory_added",
  accessory_returned_changed: "order.event_accessory_returned",
  attachment_added: "order.event_attachment_added",
  attachment_deleted: "order.event_attachment_deleted",
  note_or_contact_recorded: "order.event_contact_recorded",
  payment_recorded: "order.event_payment_recorded",
  payment_refunded: "order.event_payment_refunded",
  invoice_issued: "order.event_invoice_issued",
};

export function TimelineSection({ orderId }: { orderId: string }) {
  const { data: events } = useQuery({
    queryKey: queryKeys.orderTimeline(orderId),
    queryFn: () => api.get<TimelineEventOut[]>(`/orders/${orderId}/timeline`),
  });
  const { data: users } = useQuery({
    queryKey: queryKeys.users,
    queryFn: () => api.get<UserOut[]>("/users?include_inactive=true"),
  });

  const actorName = (id: string | null) =>
    id ? (users ?? []).find((u) => u.id === id)?.name ?? t("order.event_system") : t("order.event_system");

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.timeline")}
      </h3>
      <ol className="flex flex-col gap-2">
        {(events ?? []).map((e, i) => {
          const contactType = e.event_type === "note_or_contact_recorded"
            ? String(e.data.type ?? "") : null;
          const contactSummary = contactType ? String(e.data.summary ?? "") : null;
          return (
            <li key={i} className="flex items-start gap-3 text-sm">
              <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-slate-300" />
              <div>
                {contactType ? (
                  <p className="text-slate-700">
                    <span className="mr-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                      {t(CONTACT_TYPE_LABEL[contactType] ?? "order.contact_note")}
                    </span>
                    {contactSummary}
                  </p>
                ) : (
                  <p className="text-slate-700">{t(EVENT_LABEL[e.event_type] ?? e.event_type)}</p>
                )}
                <p className="text-xs text-slate-400">
                  {actorName(e.actor_user_id)} · {new Date(e.created_at).toLocaleString("bg-BG")}
                </p>
              </div>
            </li>
          );
        })}
        {events?.length === 0 && <p className="text-sm text-slate-400">{t("order.timeline_none")}</p>}
      </ol>
    </div>
  );
}
