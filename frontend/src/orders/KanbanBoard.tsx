/**
 * KanbanBoard (docs/15 §6.3): dnd-kit DnD across the open-kind columns.
 * The client matrix (transition-matrix.json) only dims forbidden columns and
 * blocks the drop — the server remains the single source of truth (docs/15 §9).
 * No terminal column exists on the board; terminal transitions are dialog-only.
 *
 * Issue 4 (Чака клиент as a Diagnosis sub-state): `waiting_customer` stays a
 * real backend status — nothing here touches statuses.py, the transition
 * matrix, or the approval-gate logic — it just never gets its own column.
 * Its orders render inside the `diagnostics` column instead, tagged with a
 * badge (OrderCard). Drag data always carries the order's own real
 * status_code (never "which column it's drawn in"), so dragging one of
 * these cards still reports `from: "waiting_customer"` exactly as before —
 * OrdersPage's existing approval-dialog special-case is unaffected.
 */

import {
  DndContext,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useState } from "react";
import { OPEN_STATUSES, allowedTransitions, statusName } from "../lib/statusMatrix";
import { OrderCard } from "./OrderCard";
import type { OrderListItem, UserItem } from "./types";

// Issue 4: no dedicated Kanban column for this status — its orders render
// inside DIAGNOSIS_HOST_COLUMN instead (see module docstring).
const WAITING_CUSTOMER_CODE = "waiting_customer";
const DIAGNOSIS_HOST_COLUMN = "diagnostics";
const VISIBLE_COLUMNS = OPEN_STATUSES.filter((s) => s.code !== WAITING_CUSTOMER_CODE);

function StatusColumn({
  code,
  orders,
  technicianNames,
  forbidden,
}: {
  code: string;
  orders: OrderListItem[];
  technicianNames: Map<string, string>;
  forbidden: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: code });

  return (
    <div
      ref={setNodeRef}
      className={`flex w-72 shrink-0 flex-col gap-2 rounded-lg border p-2 ${
        isOver && !forbidden ? "border-blue-400 bg-blue-50" : "border-slate-200 bg-slate-50"
      } ${forbidden ? "opacity-40" : ""}`}
    >
      <div className="flex items-center justify-between px-1 py-1">
        <h2 className="text-sm font-semibold text-slate-700">{statusName(code)}</h2>
        <span className="text-xs text-slate-400">{orders.length}</span>
      </div>
      <div className="flex flex-col gap-2">
        {orders.map((order) => (
          <OrderCard
            key={order.id}
            order={order}
            technicianName={order.technician_id ? technicianNames.get(order.technician_id) ?? null : null}
          />
        ))}
      </div>
    </div>
  );
}

export function KanbanBoard({
  orders,
  technicians,
  onDrop,
}: {
  orders: OrderListItem[];
  technicians: UserItem[];
  onDrop: (orderId: string, from: string, to: string) => void;
}) {
  const [draggingFrom, setDraggingFrom] = useState<string | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const technicianNames = new Map(technicians.map((u) => [u.id, u.name]));

  const allowedTargets = draggingFrom
    ? new Set(allowedTransitions(draggingFrom).map((t) => t.code))
    : null;

  const handleDragStart = (event: DragStartEvent) => {
    setDraggingFrom((event.active.data.current as { statusCode: string }).statusCode);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setDraggingFrom(null);
    const { active, over } = event;
    if (!over) return;
    const from = (active.data.current as { statusCode: string }).statusCode;
    const to = String(over.id);
    if (to === from) return;
    if (!OPEN_STATUSES.some((s) => s.code === to)) return;
    onDrop(String(active.id), from, to);
  };

  return (
    <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="flex gap-3 overflow-x-auto pb-4">
        {VISIBLE_COLUMNS.map((status) => (
          <StatusColumn
            key={status.code}
            code={status.code}
            orders={orders.filter((o) =>
              status.code === DIAGNOSIS_HOST_COLUMN
                ? o.status_code === status.code || o.status_code === WAITING_CUSTOMER_CODE
                : o.status_code === status.code,
            )}
            technicianNames={technicianNames}
            forbidden={
              draggingFrom !== null &&
              status.code !== draggingFrom &&
              !allowedTargets?.has(status.code)
            }
          />
        ))}
      </div>
    </DndContext>
  );
}
