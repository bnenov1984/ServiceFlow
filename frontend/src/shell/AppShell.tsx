/**
 * Business OS shell (docs/10 §1, docs/15 §2): top bar, per-app nav (Фактури/
 * Настройки grayed per PO decision), one health banner slot, mobile bottom
 * bar, idle lock.
 *
 * Business OS is the platform; RepairFlow and PropertyFlow are equal sibling
 * applications on top of it (product decision, 25.07.2026) - display names
 * only, route paths and backend module keys are unchanged (still "/", "/ps"
 * and "professional-services" respectively). PropertyFlow gets its own nav
 * section, not a submenu entry inside RepairFlow's.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { PinSwitchDialog } from "../auth/PinSwitchDialog";
import { useAuth } from "../auth/AuthContext";
import { Avatar } from "../components/Avatar";
import { PinPad } from "../components/PinPad";
import { t, type MessageKey } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { SearchBox } from "./SearchBox";

const IDLE_LOCK_MS = 5 * 60 * 1000; // FDD checklist default, PO-approved

interface AppDef {
  id: string;
  nameKey: MessageKey;
  path: string;
  /** null = always active (RepairFlow has no activation gate); otherwise the
   * companies.settings.active_modules key that must be present. */
  moduleKey: string | null;
}

// The only place the shell knows about individual apps. Adding a third
// (ConstructionFlow, ...) later is one more entry here, per BOS-06 activation.
const APPS: AppDef[] = [
  { id: "repairflow", nameKey: "app.repairflow", path: "/", moduleKey: null },
  { id: "propertyflow", nameKey: "app.propertyflow", path: "/ps", moduleKey: "professional-services" },
];

interface Health {
  status: "ok" | "degraded" | "fail";
}

function navClass(active: boolean): string {
  return `flex items-center rounded-lg px-3 py-2 text-sm font-medium min-h-touch ${
    active ? "bg-blue-50 text-blue-800" : "text-slate-600 hover:bg-slate-100"
  }`;
}

function GrayedNavItem({ label }: { label: string }) {
  return (
    <span
      title={t("nav.coming_soon")}
      aria-disabled
      className="flex cursor-not-allowed items-center rounded-lg px-3 py-2 text-sm font-medium text-slate-300 min-h-touch"
    >
      {label}
    </span>
  );
}

/** Header control: switch between the apps active for this company. Shows
 * only active apps (RepairFlow always; PropertyFlow when its module is
 * activated) - never a disabled/greyed entry for an inactive app, per the
 * same "don't show what isn't there" rule the sidebar already followed. */
function AppSwitcher({ apps, current }: { apps: AppDef[]; current: AppDef }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  if (apps.length <= 1) return null;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-semibold text-slate-700 hover:bg-slate-100 min-h-touch"
      >
        {t(current.nameKey)}
        <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <ul
          role="listbox"
          className="absolute left-0 top-full z-40 mt-1 w-40 rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {apps.map((app) => (
            <li key={app.id}>
              <button
                type="button"
                role="option"
                aria-selected={app.id === current.id}
                onClick={() => {
                  setOpen(false);
                  navigate(app.path);
                }}
                className={`block w-full px-3 py-2 text-left text-sm min-h-touch ${
                  app.id === current.id
                    ? "bg-blue-50 text-blue-800"
                    : "text-slate-700 hover:bg-slate-50"
                }`}
              >
                {t(app.nameKey)}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function useIdleLock(): [boolean, () => void] {
  const [locked, setLocked] = useState(false);

  useEffect(() => {
    let timer = setTimeout(() => setLocked(true), IDLE_LOCK_MS);
    const reset = () => {
      clearTimeout(timer);
      timer = setTimeout(() => setLocked(true), IDLE_LOCK_MS);
    };
    const events = ["mousemove", "mousedown", "keydown", "touchstart", "scroll"] as const;
    events.forEach((name) => window.addEventListener(name, reset, { passive: true }));
    return () => {
      clearTimeout(timer);
      events.forEach((name) => window.removeEventListener(name, reset));
    };
  }, []);

  return [locked, () => setLocked(false)];
}

export function AppShell() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [pinOpen, setPinOpen] = useState(false);
  const [locked, unlock] = useIdleLock();

  const activeApps = APPS.filter(
    (a) => a.moduleKey === null || me?.active_modules.includes(a.moduleKey),
  );
  const currentApp =
    APPS.find((a) => a.path !== "/" && location.pathname.startsWith(a.path)) ?? APPS[0];

  useEffect(() => {
    document.title = `${t(currentApp.nameKey)} · ${t("app.name")}`;
  }, [currentApp]);

  const { data: health, isError: healthError } = useQuery({
    queryKey: queryKeys.health,
    queryFn: () => api.get<Health>("/platform/health"),
    refetchInterval: 60_000,
    retry: 1,
  });

  const healthProblem = healthError
    ? t("health.unreachable")
    : health && health.status !== "ok"
      ? t(`health.${health.status}`)
      : null;

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-2">
        <Link to="/" className="text-lg font-bold text-slate-900">
          {t("app.name")}
        </Link>
        <AppSwitcher apps={activeApps} current={currentApp} />
        <SearchBox />
        <button
          type="button"
          onClick={() => navigate("/orders/new")}
          className="ml-auto whitespace-nowrap rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 min-h-touch"
        >
          {t("shell.new_order")}
        </button>
        <button
          type="button"
          onClick={() => setPinOpen(true)}
          title={t("shell.switch_user")}
          className="flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-slate-100 min-h-touch"
        >
          <Avatar name={me?.name ?? "?"} />
          <span className="hidden text-sm font-medium text-slate-700 md:inline">{me?.name}</span>
        </button>
      </header>

      {healthProblem && (
        <div role="alert" className="bg-red-600 px-4 py-2 text-sm font-medium text-white">
          {healthProblem}
        </div>
      )}

      <div className="flex flex-1">
        <nav
          aria-label={`${t(currentApp.nameKey)} navigation`}
          className="hidden w-52 shrink-0 flex-col gap-1 border-r border-slate-200 bg-white p-3 md:flex"
        >
          {/* Own menu per app (not a submenu of another app, product decision
              25.07.2026): only the current app's nav items render here. */}
          <p className="mb-1 px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
            {t(currentApp.nameKey)}
          </p>
          {currentApp.id === "repairflow" && (
            <>
              <NavLink to="/" end className={({ isActive }) => navClass(isActive)}>
                {t("nav.dashboard")}
              </NavLink>
              <NavLink to="/orders" className={({ isActive }) => navClass(isActive)}>
                {t("nav.orders")}
              </NavLink>
              <NavLink to="/customers" className={({ isActive }) => navClass(isActive)}>
                {t("nav.customers")}
              </NavLink>
            </>
          )}
          {currentApp.id === "propertyflow" && (
            <NavLink to="/ps" end className={({ isActive }) => navClass(isActive)}>
              {t("nav.dashboard")}
            </NavLink>
          )}
          <GrayedNavItem label={t("nav.invoices")} />
          <GrayedNavItem label={t("nav.settings")} />
          <button
            type="button"
            onClick={() => void logout().then(() => navigate("/login"))}
            className="mt-auto rounded-lg px-3 py-2 text-left text-sm text-slate-500 hover:bg-slate-100 min-h-touch"
          >
            {t("shell.logout")}
          </button>
        </nav>

        {/* min-w-0: без него flex елементът не се свива под ширината на
            съдържанието си и широки екрани (Kanban) разпъват цялото приложение
            вместо да скролират в собствения си overflow контейнер. */}
        <main className="min-w-0 flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom bar (docs/15 §8): active sections + new-order shortcut.
          RepairFlow-only for now (matches its pre-rebrand scope) - not part
          of this rebrand's scope, tracked as a follow-up. */}
      <nav aria-label="RepairFlow mobile navigation" className="sticky bottom-0 flex border-t border-slate-200 bg-white md:hidden">
        {[
          { to: "/", label: t("nav.dashboard") },
          { to: "/orders", label: t("nav.orders") },
          { to: "/customers", label: t("nav.customers") },
        ].map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex flex-1 items-center justify-center py-3 text-sm font-medium min-h-touch ${
                isActive ? "text-blue-700" : "text-slate-500"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <PinSwitchDialog open={pinOpen} onClose={() => setPinOpen(false)} />

      {locked && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-slate-900/80 p-4">
          <div className="w-full max-w-md rounded-lg bg-white p-6">
            <h2 className="mb-1 text-lg font-semibold">{t("shell.locked_title")}</h2>
            <p className="mb-4 text-sm text-slate-500">{t("shell.locked_hint")}</p>
            <LockedPanel onUnlocked={unlock} />
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Idle lock (ADR-008): inline user list + PIN pad, NO dismissal path other than
 * a correct PIN (identity re-verified via pin-switch — self included) or logout.
 */
function LockedPanel({ onUnlocked }: { onUnlocked: () => void }) {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<LockUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: users } = useQuery({
    queryKey: queryKeys.users,
    queryFn: () => api.get<LockUser[]>("/users"),
  });

  const submitPin = async (pin: string) => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/pin-switch", { user_id: selected.id, pin });
      queryClient.clear();
      onUnlocked();
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {!selected ? (
        <ul className="flex flex-col gap-2">
          {(users ?? []).map((u) => (
            <li key={u.id}>
              <button
                type="button"
                onClick={() => setSelected(u)}
                className="flex w-full items-center gap-3 rounded-lg border border-slate-200 px-4 py-3 text-left hover:bg-slate-50 min-h-touch"
              >
                <Avatar name={u.name} />
                <span className="font-medium text-slate-800">
                  {u.id === me?.user_id ? t("shell.you_suffix", { name: u.name }) : u.name}
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
          <PinPad onSubmit={(pin) => void submitPin(pin)} disabled={busy} />
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
      <button
        type="button"
        onClick={() => void logout().then(() => navigate("/login"))}
        className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50 min-h-touch"
      >
        {t("shell.logout")}
      </button>
    </div>
  );
}

interface LockUser {
  id: string;
  name: string;
  is_owner: boolean;
  is_active: boolean;
}
