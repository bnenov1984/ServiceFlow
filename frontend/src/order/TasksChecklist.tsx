/** TasksChecklist (docs/15 §6.5, docs/02 §5): not mandatory, completion never
 * auto-changes order status (humans move orders — 02 §5). */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type KeyboardEvent } from "react";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

interface TaskOut {
  id: string;
  title: string;
  is_done: boolean;
  is_call: boolean;
  due_on: string | null;
}

export function TasksChecklist({ orderId }: { orderId: string }) {
  const [title, setTitle] = useState("");
  const [isCall, setIsCall] = useState(false);
  const queryClient = useQueryClient();

  const { data: tasks } = useQuery({
    queryKey: queryKeys.orderTasks(orderId),
    queryFn: () => api.get<TaskOut[]>(`/orders/${orderId}/tasks`),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.orderTasks(orderId) });

  const addTask = async () => {
    const value = title.trim();
    if (!value) return;
    setTitle("");
    setIsCall(false);
    await api.post(`/orders/${orderId}/tasks`, { title: value, is_call: isCall });
    await invalidate();
  };

  const toggleDone = async (task: TaskOut) => {
    await api.patch(`/tasks/${task.id}`, { is_done: !task.is_done });
    await invalidate();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      void addTask();
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.tasks")}
      </h3>
      <ul className="mb-3 flex flex-col gap-1">
        {(tasks ?? []).map((task) => (
          <li key={task.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={task.is_done}
              onChange={() => void toggleDone(task)}
              className="h-5 w-5"
            />
            <span className={task.is_done ? "text-slate-400 line-through" : "text-slate-700"}>
              {task.title}
            </span>
            {task.is_call && (
              <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                {t("order.task_call_badge")}
              </span>
            )}
          </li>
        ))}
        {tasks?.length === 0 && <p className="text-sm text-slate-400">{t("order.tasks_none")}</p>}
      </ul>
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={t("order.task_add_placeholder")}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
        />
        <label className="flex items-center gap-1 text-xs text-slate-500">
          <input type="checkbox" checked={isCall} onChange={(e) => setIsCall(e.target.checked)} />
          {t("order.task_call_flag")}
        </label>
        <button
          type="button"
          onClick={() => void addTask()}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch"
        >
          {t("intake.accessory_add")}
        </button>
      </div>
    </div>
  );
}
