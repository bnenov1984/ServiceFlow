/**
 * PIN switch (ADR-008, docs/15 §6.6): pick a user, enter PIN, swap the acting
 * identity. On success every *other* cached query is wiped — a rare,
 * deliberate full reset so nothing from the previous actor lingers
 * (docs/15 §5.3) — but "me" itself is seeded directly from the response,
 * never torn down, matching LoginPage.tsx's already-established pattern:
 * `queryClient.clear()`/`removeQueries` on "me" destroys the query object
 * AuthProvider's own `useQuery` observer is subscribed to, and that observer
 * does not reliably pick up a query recreated from scratch afterward -
 * confirmed by this exact bug (the header kept the previous user's name
 * until an unrelated navigation/remount forced a fresh fetch).
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { t } from "../i18n/bg";
import { ApiError, api, setCsrfToken } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { Avatar } from "../components/Avatar";
import { Dialog } from "../components/Dialog";
import { PinPad } from "../components/PinPad";
import { useAuth, type Me } from "./AuthContext";

interface UserItem {
  id: string;
  name: string;
  is_owner: boolean;
  is_active: boolean;
  has_pin: boolean;
}

export function PinSwitchDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<UserItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: users } = useQuery({
    queryKey: queryKeys.users,
    queryFn: () => api.get<UserItem[]>("/users"),
    enabled: open,
  });

  // Dialog never unmounts its children just because `open` becomes false
  // (see Dialog.tsx) — only `selected` going back to null actually tears
  // down the selected-user branch (and with it, the mounted PinPad holding
  // whatever partial PIN was typed). Routing every close path (X, Escape,
  // successful submit) through this one function is what makes a reopened
  // dialog start clean, instead of only resetting on success like before.
  // `busy` is deliberately left alone here: if a request is still in
  // flight when the dialog closes, leaving `busy` true keeps confirm
  // guarded on reopen until that request resolves, rather than allowing a
  // second, overlapping /auth/pin-switch call.
  const handleClose = () => {
    setSelected(null);
    setError(null);
    onClose();
  };

  const submitPin = async (pin: string) => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const switchedMe = await api.post<Me>("/auth/pin-switch", { user_id: selected.id, pin });
      // Synchronous, not a reliance on AuthContext's own useEffect picking
      // up the new csrf_token off the query cache - see LoginPage.tsx for
      // the same ordering and why it matters (a request fired before that
      // effect runs would otherwise carry the previous user's token).
      setCsrfToken(switchedMe.csrf_token);
      queryClient.setQueryData(queryKeys.me, switchedMe);
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
      handleClose();
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} title={t("auth.pin_title")}>
      {!selected ? (
        <ul className="flex flex-col gap-2">
          {(users ?? [])
            .filter((u) => u.id !== me?.user_id)
            .map((u) => (
              <li key={u.id}>
                <button
                  type="button"
                  disabled={!u.has_pin}
                  title={u.has_pin ? undefined : t("pin.switch_no_pin_hint")}
                  onClick={() => setSelected(u)}
                  className="flex w-full items-center gap-3 rounded-lg border border-slate-200 px-4 py-3 text-left hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent min-h-touch"
                >
                  <Avatar name={u.name} />
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium text-slate-800">{u.name}</span>
                    {!u.has_pin && (
                      <span className="block text-xs text-slate-400">{t("pin.switch_no_pin_hint")}</span>
                    )}
                  </span>
                </button>
              </li>
            ))}
        </ul>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <div className="flex items-center gap-3">
            <Avatar name={selected.name} />
            <span className="font-medium">{selected.name}</span>
          </div>
          <PinPad onSubmit={submitPin} disabled={busy} />
          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
          <button
            type="button"
            onClick={() => setSelected(null)}
            className="text-sm text-slate-500 hover:underline"
          >
            {t("common.cancel")}
          </button>
        </div>
      )}
    </Dialog>
  );
}
