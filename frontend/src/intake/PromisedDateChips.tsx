/** Promised-date quick chips (docs/15 §6.4: Днес/Утре/3 дни/Седмица/дата). */

import { t } from "../i18n/bg";

function isoInDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

const CHIPS: { labelKey: Parameters<typeof t>[0]; days: number }[] = [
  { labelKey: "intake.promised_today", days: 0 },
  { labelKey: "intake.promised_tomorrow", days: 1 },
  { labelKey: "intake.promised_3days", days: 3 },
  { labelKey: "intake.promised_week", days: 7 },
];

export function PromisedDateChips({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (iso: string | null) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {CHIPS.map((chip) => {
        const iso = isoInDays(chip.days);
        const active = value === iso;
        return (
          <button
            key={chip.days}
            type="button"
            onClick={() => onChange(active ? null : iso)}
            aria-pressed={active}
            className={`rounded-full border px-3 py-1.5 text-sm font-medium min-h-touch ${
              active
                ? "border-blue-600 bg-blue-600 text-white"
                : "border-slate-300 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {t(chip.labelKey)}
          </button>
        );
      })}
      <input
        type="date"
        value={value && !CHIPS.some((c) => isoInDays(c.days) === value) ? value : ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm min-h-touch"
        aria-label={t("intake.promised_custom")}
      />
    </div>
  );
}
