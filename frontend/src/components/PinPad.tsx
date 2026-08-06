/** Large-button PIN pad (docs/15 §6.6) — counter-friendly touch targets. */

import { useState } from "react";
import { t } from "../i18n/bg";

export function PinPad({
  onSubmit,
  disabled = false,
}: {
  onSubmit: (pin: string) => void;
  disabled?: boolean;
}) {
  const [pin, setPin] = useState("");

  // Functional updater, not `setPin(pin + digit)`: two clicks dispatched
  // close together (rapid real touch-typing, or scripted rapid clicks) each
  // read `pin` from their own render's closure before React commits the
  // first update, so a plain closure read silently drops digits under
  // React 18's automatic batching. The updater form always sees the latest
  // pending state regardless of how many presses land in the same batch.
  const press = (digit: string) => {
    setPin((prev) => (prev.length < 8 ? prev + digit : prev));
  };

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        aria-label="PIN"
        className="flex h-10 items-center gap-2 text-2xl tracking-widest text-slate-800"
      >
        {pin.length === 0 ? (
          <span className="text-base text-slate-400">{t("auth.pin_hint")}</span>
        ) : (
          "●".repeat(pin.length)
        )}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
          <button
            key={d}
            type="button"
            disabled={disabled}
            onClick={() => press(d)}
            className="h-14 w-14 rounded-lg bg-slate-100 text-xl font-semibold hover:bg-slate-200 disabled:opacity-50"
          >
            {d}
          </button>
        ))}
        {/* Глифи вместо текст на служебните бутони: „Потвърди“/„Изтрий“ не се
            събират в 56px клетка (прецедент: ✕ в Dialog.tsx). */}
        <button
          type="button"
          disabled={disabled || pin.length === 0}
          onClick={() => setPin("")}
          aria-label={t("auth.pin_clear")}
          title={t("auth.pin_clear")}
          className="h-14 w-14 rounded-lg bg-slate-100 text-xl hover:bg-slate-200 disabled:opacity-50"
        >
          ⌫
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => press("0")}
          className="h-14 w-14 rounded-lg bg-slate-100 text-xl font-semibold hover:bg-slate-200 disabled:opacity-50"
        >
          0
        </button>
        <button
          type="button"
          disabled={disabled || pin.length === 0}
          onClick={() => {
            onSubmit(pin);
            setPin("");
          }}
          aria-label={t("auth.pin_confirm")}
          title={t("auth.pin_confirm")}
          className="h-14 w-14 rounded-lg bg-blue-600 text-xl font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          ✓
        </button>
      </div>
    </div>
  );
}
