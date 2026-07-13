/** Ready chips + free-add (docs/15 §6.4, PO-approved defaults: Зарядно/СИМ/Кутия/Ключ). */

import { useState, type KeyboardEvent } from "react";
import { t } from "../i18n/bg";

const DEFAULT_CHIPS = ["Зарядно", "СИМ", "Кутия", "Ключ"];

export function AccessoriesChecklist({
  selected,
  onToggle,
}: {
  selected: string[];
  // Toggle-by-name, not "here's the next array" — the parent computes the diff
  // inside a functional state update so two chip clicks landing in the same
  // batched React cycle can never clobber each other (found via browser
  // verification: a same-tick double click silently dropped the first pick
  // when this component used to compute and hand back a full next array from
  // its `selected` prop, which the second click's handler still saw as stale).
  onToggle: (name: string) => void;
}) {
  const [custom, setCustom] = useState("");

  const addCustom = () => {
    const value = custom.trim();
    if (value) onToggle(value);
    setCustom("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addCustom();
    }
  };

  const extra = selected.filter((s) => !DEFAULT_CHIPS.includes(s));

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {[...DEFAULT_CHIPS, ...extra].map((name) => {
          const active = selected.includes(name);
          return (
            <button
              key={name}
              type="button"
              onClick={() => onToggle(name)}
              aria-pressed={active}
              className={`rounded-full border px-3 py-1.5 text-sm font-medium min-h-touch ${
                active
                  ? "border-blue-600 bg-blue-600 text-white"
                  : "border-slate-300 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {name}
            </button>
          );
        })}
      </div>
      <div className="mt-2 flex gap-2">
        <input
          type="text"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={t("intake.accessory_add_placeholder")}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
        />
        <button
          type="button"
          onClick={addCustom}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 min-h-touch"
        >
          {t("intake.accessory_add")}
        </button>
      </div>
    </div>
  );
}
