/** One-time, non-blocking nudge to set a PIN after first login (docs/business-os
 * PIN self-service task, requirement 7) — never blocks the app, never repeats
 * once dismissed or once a PIN exists. "Once" is tracked client-side only
 * (localStorage, keyed by user id, same `bos.` namespace as shell/lastApp.ts)
 * — a pure UI convenience, not a server-side flag, so it adds no backend
 * surface of its own. */

import { useState } from "react";
import { Dialog } from "../components/Dialog";
import { t } from "../i18n/bg";
import { useAuth } from "./AuthContext";
import { SetPinForm } from "./SetPinForm";

function dismissedKey(userId: string): string {
  return `bos.pinPromptDismissed.${userId}`;
}

export function PinSetupPrompt() {
  const { me } = useAuth();
  const [dismissed, setDismissed] = useState(false);
  const [open, setOpen] = useState(false);

  if (!me || me.has_pin || dismissed || localStorage.getItem(dismissedKey(me.user_id))) {
    return null;
  }

  const dismiss = () => {
    localStorage.setItem(dismissedKey(me.user_id), "1");
    setDismissed(true);
  };

  return (
    <>
      <div
        role="status"
        className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-blue-100 bg-blue-50 px-4 py-2 text-sm"
      >
        <span className="font-medium text-blue-900">{t("pin.setup_prompt_title")}</span>
        <span className="text-blue-700">{t("pin.setup_prompt_hint")}</span>
        <div className="ml-auto flex items-center gap-3">
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="font-medium text-blue-700 hover:underline"
          >
            {t("pin.locked_set_action")}
          </button>
          <button
            type="button"
            onClick={dismiss}
            className="text-blue-500 hover:text-blue-700"
          >
            {t("pin.setup_prompt_dismiss")}
          </button>
        </div>
      </div>

      <Dialog open={open} onClose={() => setOpen(false)} title={t("pin.locked_set_action")}>
        <SetPinForm
          onDone={() => { setOpen(false); dismiss(); }}
          onCancel={() => setOpen(false)}
        />
      </Dialog>
    </>
  );
}
