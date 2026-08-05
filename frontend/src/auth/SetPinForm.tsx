/** Shared two-step "enter new PIN, then confirm it" flow — one component
 * behind the three places a user can set/replace their own PIN (Settings'
 * "Моят PIN" card, the idle-lock screen's no-PIN escape hatch, and the
 * one-time post-login setup prompt), all backed by the same self-service
 * `POST /auth/pin` (docs/business-os PIN self-service task). Reuses the
 * existing PinPad, so validation/hashing stay identical to every other PIN
 * entry point (pin-switch, employee creation). */

import { useState } from "react";
import { PinPad } from "../components/PinPad";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { useAuth } from "./AuthContext";

const MIN_PIN_LENGTH = 4;

export function SetPinForm({
  onDone,
  onCancel,
}: {
  onDone: () => void;
  onCancel?: () => void;
}) {
  const { refresh } = useAuth();
  const [step, setStep] = useState<"enter" | "confirm">("enter");
  const [firstPin, setFirstPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const restart = (message: string | null) => {
    setStep("enter");
    setFirstPin("");
    setError(message);
  };

  const handleFirst = (pin: string) => {
    if (pin.length < MIN_PIN_LENGTH) {
      setError(t("pin.set_form_too_short"));
      return;
    }
    setFirstPin(pin);
    setError(null);
    setStep("confirm");
  };

  const handleConfirm = async (pin: string) => {
    if (pin !== firstPin) {
      restart(t("pin.set_form_mismatch"));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/auth/pin", { pin });
      await refresh();
      onDone();
    } catch (err) {
      restart(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col items-center gap-3">
      <p className="text-sm font-medium text-slate-700">
        {step === "enter" ? t("pin.set_form_enter_label") : t("pin.set_form_confirm_label")}
      </p>
      {step === "confirm" && (
        <p className="text-xs text-slate-500">{t("pin.set_form_confirm_hint")}</p>
      )}
      <PinPad
        key={step}
        onSubmit={(pin) => (step === "enter" ? handleFirst(pin) : void handleConfirm(pin))}
        disabled={submitting}
      />
      {error && (
        <p role="alert" className="text-sm text-red-700">{error}</p>
      )}
      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="text-sm text-slate-500 hover:underline"
        >
          {t("common.cancel")}
        </button>
      )}
    </div>
  );
}
