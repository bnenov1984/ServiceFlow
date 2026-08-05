/** "Моят PIN" (docs/business-os PIN self-service task): set/change the
 * current user's own PIN — the same self-service `SetPinForm` the idle-lock
 * screen and the post-login prompt use, just reachable on demand here
 * instead of only when locked out or freshly logged in. */

import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { SetPinForm } from "../auth/SetPinForm";
import { t } from "../i18n/bg";

export function MyPinCard() {
  const { me } = useAuth();
  const [editing, setEditing] = useState(false);

  if (!me) return null;

  return (
    <div className="mb-6 max-w-lg rounded-lg border border-slate-200 bg-white p-6">
      <h2 className="mb-2 font-semibold text-slate-900">{t("pin.my_pin_title")}</h2>
      {editing ? (
        <SetPinForm onDone={() => setEditing(false)} onCancel={() => setEditing(false)} />
      ) : (
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-slate-600">
            {me.has_pin ? t("pin.my_pin_set_hint") : t("pin.my_pin_not_set_hint")}
          </p>
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="shrink-0 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 min-h-touch"
          >
            {me.has_pin ? t("pin.my_pin_change_action") : t("pin.my_pin_set_action")}
          </button>
        </div>
      )}
    </div>
  );
}
