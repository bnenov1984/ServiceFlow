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
 *
 * Global vs application-owned controls (26.07.2026, found via manual testing:
 * RepairFlow's search and "Нова поръчка" were leaking into every app's top
 * bar): GlobalHeader carries only platform-level controls (brand, app
 * switcher, account menu) and never changes by route. RepairFlowToolbar owns
 * RepairFlow's own search + primary action and renders only when
 * currentApp.id === "repairflow" - a plain conditional render (unmounts, not
 * CSS-hidden), so no stale search state survives a switch to PropertyFlow and
 * a direct load of /ps never flashes RepairFlow controls. PropertyFlow has no
 * toolbar of its own yet - none of its actions exist as reusable components
 * to move in, and this task does not invent new ones.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { PinSetupPrompt } from "../auth/PinSetupPrompt";
import { PinSwitchDialog } from "../auth/PinSwitchDialog";
import { SetPinForm } from "../auth/SetPinForm";
import { useAuth } from "../auth/AuthContext";
import { Avatar } from "../components/Avatar";
import { Dialog } from "../components/Dialog";
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
  /** The companies.settings.active_modules key that must be present. Every
   * app is a real, backend-gated entitlement (PO decision, 01.08.2026) —
   * `null` was RepairFlow's old "always active" special case and no longer
   * exists. */
  moduleKey: string | null;
}

// The only place the shell knows about individual apps. Adding a third
// (ConstructionFlow, ...) later is one more entry here, per BOS-06 activation.
const APPS: AppDef[] = [
  { id: "repairflow", nameKey: "app.repairflow", path: "/", moduleKey: "repairflow" },
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
function AppSwitcher({ apps, current }: { apps: AppDef[]; current: AppDef | undefined }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  // apps.length > 1 (both active) is the only case current is guaranteed
  // defined in - see AppShell's own currentApp comment.
  if (apps.length <= 1 || !current) return null;

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

/** Header account control: avatar + name trigger opens a small actions menu
 * (self-service PIN, switch user, manual lock, logout). Previously this
 * button only opened PinSwitchDialog directly - the other actions had no
 * header-level entry point before this task (self-service PIN lived only
 * in Settings' "Моят PIN" card, and there was no way to lock the screen
 * on demand, only via the 5-minute idle timeout). Same bespoke
 * open/absolute-list idiom as AppSwitcher, just role="menu"/"menuitem"
 * (actions, not a navigation choice). */
function AccountMenu({
  onOpenPinForm, onSwitchUser, onLock,
}: { onOpenPinForm: () => void; onSwitchUser: () => void; onLock: () => void }) {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  if (!me) return null;

  const act = (fn: () => void) => {
    setOpen(false);
    fn();
  };

  return (
    <div className="relative ml-auto">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={t("shell.account_menu_label")}
        className="flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-slate-100 min-h-touch"
      >
        <Avatar name={me.name} />
        <span className="hidden text-sm font-medium text-slate-700 md:inline">{me.name}</span>
      </button>
      {open && (
        <ul
          role="menu"
          className="absolute right-0 top-full z-40 mt-1 w-56 rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          <li role="none">
            <button
              type="button"
              role="menuitem"
              onClick={() => act(onOpenPinForm)}
              className="block w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 min-h-touch"
            >
              {me.has_pin ? t("pin.my_pin_change_action") : t("pin.my_pin_set_action")}
            </button>
          </li>
          <li role="none">
            <button
              type="button"
              role="menuitem"
              onClick={() => act(onSwitchUser)}
              className="block w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 min-h-touch"
            >
              {t("shell.switch_user")}
            </button>
          </li>
          <li role="none">
            <button
              type="button"
              role="menuitem"
              onClick={() => act(onLock)}
              className="block w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 min-h-touch"
            >
              {t("shell.lock_screen_action")}
            </button>
          </li>
          <li role="none">
            <button
              type="button"
              role="menuitem"
              onClick={() => act(() => void logout().catch(() => {}).finally(() => navigate("/login")))}
              className="block w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 min-h-touch"
            >
              {t("shell.logout")}
            </button>
          </li>
        </ul>
      )}
    </div>
  );
}

/** Platform-level top bar only: brand, app switcher, account menu. Never
 * RepairFlow (or any other app)-specific - see RepairFlowToolbar for that. */
function GlobalHeader({
  activeApps, currentApp, onOpenPinForm, onSwitchUser, onLock,
}: {
  activeApps: AppDef[];
  currentApp: AppDef | undefined;
  onOpenPinForm: () => void;
  onSwitchUser: () => void;
  onLock: () => void;
}) {
  return (
    <header className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-2">
      <Link to="/" className="text-lg font-bold text-slate-900">
        {t("app.name")}
      </Link>
      <AppSwitcher apps={activeApps} current={currentApp} />
      <AccountMenu onOpenPinForm={onOpenPinForm} onSwitchUser={onSwitchUser} onLock={onLock} />
    </header>
  );
}

/** RepairFlow's own contextual toolbar: client/device/model/serial search
 * (device-type-agnostic wording, PO decision 01.08.2026 — RepairFlow covers
 * more than phones) and the "Нова поръчка" primary action. Rendered only for
 * currentApp.id ===
 * "repairflow" (see AppShell below) - reuses the existing SearchBox
 * component and navigate("/orders/new") call as-is, just relocated. */
function RepairFlowToolbar() {
  const navigate = useNavigate();

  return (
    <div className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-2">
      <SearchBox />
      <button
        type="button"
        onClick={() => navigate("/orders/new")}
        className="ml-auto whitespace-nowrap rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 min-h-touch"
      >
        {t("shell.new_order")}
      </button>
    </div>
  );
}

function useIdleLock(): [boolean, () => void, () => void] {
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

  // Manual lock ("Заключи екрана" in the account menu) reuses the same
  // `locked` state and LockedPanel/onUnlocked flow the idle timeout drives -
  // no second lock UI, just a different trigger for the same overlay.
  return [locked, () => setLocked(false), () => setLocked(true)];
}

export function AppShell() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [pinSwitchOpen, setPinSwitchOpen] = useState(false);
  const [pinFormOpen, setPinFormOpen] = useState(false);
  const [locked, unlock, lock] = useIdleLock();

  const activeApps = APPS.filter(
    (a) => a.moduleKey === null || me?.active_modules.includes(a.moduleKey),
  );
  // Falls back to the first *entitled* app, never APPS[0]/RepairFlow
  // unconditionally — a company with zero active apps (reachable on a
  // Core-only route like "/settings/employees") has no current app at all,
  // and none of RepairFlow's own chrome (toolbar, nav, mobile bar) may
  // render for it (App.tsx's IndexRoute is the first line of defense for
  // "/" itself; this is the shell's own second line, e.g. for a direct
  // deep link).
  const currentApp: AppDef | undefined =
    APPS.find((a) => a.path !== "/" && location.pathname.startsWith(a.path))
    ?? activeApps[0];

  useEffect(() => {
    document.title = currentApp ? `${t(currentApp.nameKey)} · ${t("app.name")}` : t("app.name");
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
      <GlobalHeader
        activeApps={activeApps}
        currentApp={currentApp}
        onOpenPinForm={() => setPinFormOpen(true)}
        onSwitchUser={() => setPinSwitchOpen(true)}
        onLock={lock}
      />
      {currentApp?.id === "repairflow" && <RepairFlowToolbar />}
      <PinSetupPrompt />

      {healthProblem && (
        <div role="alert" className="bg-red-600 px-4 py-2 text-sm font-medium text-white">
          {healthProblem}
        </div>
      )}

      <div className="flex flex-1">
        <nav
          aria-label={currentApp ? `${t(currentApp.nameKey)} navigation` : t("app.name")}
          className="hidden w-52 shrink-0 flex-col gap-1 border-r border-slate-200 bg-white p-3 md:flex"
        >
          {/* Own menu per app (not a submenu of another app, product decision
              25.07.2026): only the current app's nav items render here. */}
          {currentApp && (
            <p className="mb-1 px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
              {t(currentApp.nameKey)}
            </p>
          )}
          {currentApp?.id === "repairflow" && (
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
          {currentApp?.id === "propertyflow" && (
            <NavLink to="/ps" end className={({ isActive }) => navClass(isActive)}>
              {t("nav.dashboard")}
            </NavLink>
          )}
          <GrayedNavItem label={t("nav.invoices")} />
          {me?.is_owner ? (
            <NavLink to="/settings/employees" className={({ isActive }) => navClass(isActive)}>
              {t("nav.settings")}
            </NavLink>
          ) : (
            <GrayedNavItem label={t("nav.settings")} />
          )}
          <button
            type="button"
            onClick={() => void logout().catch(() => {}).finally(() => navigate("/login"))}
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
          RepairFlow-only for now (matches its pre-rebrand scope; PropertyFlow
          has no mobile nav of its own yet, same scope boundary its desktop
          toolbar already respects) - gated the same as every other RepairFlow
          control so it never renders for a company without that entitlement. */}
      {currentApp?.id === "repairflow" && (
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
      )}

      <PinSwitchDialog open={pinSwitchOpen} onClose={() => setPinSwitchOpen(false)} />

      {/* Mounted only while open, unlike PinSwitchDialog's always-mounted-but-
          toggled pattern - SetPinForm renders a PinPad immediately (no
          "pick a user first" gating step), so leaving it permanently mounted
          would put a second, merely CSS-hidden set of digit buttons in the
          DOM at all times, colliding with LockedPanel's own PinPad whenever
          the screen is locked. */}
      {pinFormOpen && (
        <Dialog
          open
          onClose={() => setPinFormOpen(false)}
          title={me?.has_pin ? t("pin.my_pin_change_action") : t("pin.my_pin_set_action")}
        >
          <SetPinForm onDone={() => setPinFormOpen(false)} onCancel={() => setPinFormOpen(false)} />
        </Dialog>
      )}

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
 *
 * A user with no PIN set (every vendor-provisioned owner, until they use
 * self-service PIN setup) must never reach the PinPad — pin-switch would
 * unconditionally reject them, indistinguishable from a wrong PIN. Selecting
 * yourself with no PIN instead offers to set one on the spot (unlocking
 * immediately after, same trust boundary pin-switch itself already has — no
 * password re-entry) or to log out and back in with a password. Any *other*
 * pin-less user's entry is disabled outright: nothing productive can happen
 * from this screen for someone else's missing PIN.
 */
export function LockedPanel({ onUnlocked }: { onUnlocked: () => void }) {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<LockUser | null>(null);
  const [settingPin, setSettingPin] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: users } = useQuery({
    queryKey: queryKeys.users,
    queryFn: () => api.get<LockUser[]>("/users"),
  });

  const selectUser = (u: LockUser) => {
    setSelected(u);
    setSettingPin(false);
    setError(null);
  };

  const cancelSelection = () => {
    setSelected(null);
    setSettingPin(false);
    setError(null);
  };

  const loginWithPassword = () =>
    void logout().catch(() => {}).finally(() => navigate("/login"));

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

  const isSelf = selected && selected.id === me?.user_id;

  return (
    <div className="flex flex-col gap-3">
      {!selected ? (
        <ul className="flex flex-col gap-2">
          {(users ?? []).map((u) => {
            const self = u.id === me?.user_id;
            const disabled = !u.has_pin && !self;
            return (
              <li key={u.id}>
                <button
                  type="button"
                  disabled={disabled}
                  title={disabled ? t("pin.switch_no_pin_hint") : undefined}
                  onClick={() => selectUser(u)}
                  className="flex w-full items-center gap-3 rounded-lg border border-slate-200 px-4 py-3 text-left hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent min-h-touch"
                >
                  <Avatar name={u.name} />
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium text-slate-800">
                      {self ? t("shell.you_suffix", { name: u.name }) : u.name}
                    </span>
                    {!u.has_pin && (
                      <span className="block text-xs text-slate-400">
                        {t("pin.switch_no_pin_hint")}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : isSelf && !selected.has_pin ? (
        <div className="flex flex-col items-center gap-4">
          <div className="flex items-center gap-3">
            <Avatar name={selected.name} />
            <span className="font-medium">{selected.name}</span>
          </div>
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-center">
            <p className="font-medium text-amber-900">{t("pin.locked_no_pin_title")}</p>
            <p className="mt-1 text-sm text-amber-800">{t("pin.locked_no_pin_hint")}</p>
          </div>
          {settingPin ? (
            <SetPinForm onDone={onUnlocked} onCancel={() => setSettingPin(false)} />
          ) : (
            <div className="flex flex-col items-center gap-2">
              <button
                type="button"
                onClick={() => setSettingPin(true)}
                className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 min-h-touch"
              >
                {t("pin.locked_set_action")}
              </button>
              <button
                type="button"
                onClick={loginWithPassword}
                className="text-sm font-medium text-blue-700 hover:underline"
              >
                {t("pin.locked_login_with_password")}
              </button>
            </div>
          )}
          <button
            type="button"
            onClick={cancelSelection}
            className="text-sm text-slate-500 hover:underline"
          >
            {t("common.cancel")}
          </button>
        </div>
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
            onClick={cancelSelection}
            className="text-sm text-slate-500 hover:underline"
          >
            {t("common.cancel")}
          </button>
        </div>
      )}
      <button
        type="button"
        onClick={loginWithPassword}
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
  has_pin: boolean;
}
