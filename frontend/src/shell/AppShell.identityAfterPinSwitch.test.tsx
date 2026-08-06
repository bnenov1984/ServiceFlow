import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { queryKeys } from "../lib/queryKeys";
import { AppShell } from "./AppShell";

const mockGet = vi.fn();
const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: { ...actual.api, get: (...args: unknown[]) => mockGet(...args), post: (...args: unknown[]) => mockPost(...args) },
  };
});

const OWNER = {
  user_id: "u1", name: "Мария", email: "m@m.bg", is_owner: true, language: "bg",
  company_id: "c1", csrf_token: "csrf-owner", active_modules: ["repairflow"],
  seat_limit: null, seat_usage: 2, has_pin: true,
};
const WORKER = {
  user_id: "u2", name: "Иво", email: "ivo@m.bg", is_owner: false, language: "bg",
  company_id: "c1", csrf_token: "csrf-worker", active_modules: ["repairflow"],
  seat_limit: null, seat_usage: 2, has_pin: true,
};
const USERS_LIST = [
  { id: "u1", name: "Мария", is_owner: true, is_active: true, has_pin: true },
  { id: "u2", name: "Иво", is_owner: false, is_active: true, has_pin: true },
];

// Renders through the real AuthProvider + QueryClient (unlike
// AppShell.test.tsx's mocked useAuth, which cannot exercise this bug at
// all - the stale header lived entirely in how the "me" query cache was
// handled, a layer a mocked useAuth() bypasses). `activeMe` is mutated by
// the mocked /auth/pin-switch handler, mirroring how the real backend
// session actually changes identity - GET /auth/me always reflects
// whichever user last "won" a switch, exactly like the confirmed bug
// report (GET /auth/me immediately returns the new user; only the
// already-rendered header didn't know to ask again).
function renderShell() {
  let activeMe: typeof OWNER | typeof WORKER = OWNER;
  mockGet.mockImplementation((path: string) => {
    if (path === "/auth/me") return Promise.resolve(activeMe);
    if (path === "/platform/health") return Promise.resolve({ status: "ok" });
    if (path === "/users") return Promise.resolve(USERS_LIST);
    return Promise.reject(new Error(`unexpected GET ${path}`));
  });
  mockPost.mockImplementation((path: string, body?: unknown) => {
    if (path === "/auth/pin-switch") {
      const targetId = (body as { user_id: string }).user_id;
      activeMe = targetId === "u1" ? OWNER : WORKER;
      return Promise.resolve(activeMe);
    }
    if (path === "/auth/logout") {
      return Promise.resolve({ ok: true });
    }
    return Promise.reject(new Error(`unexpected POST ${path}`));
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<div>REPAIRFLOW_DASHBOARD</div>} />
            </Route>
            <Route path="/login" element={<div>LOGIN_PAGE</div>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
  return { ...utils, queryClient };
}

async function switchViaAccountMenu(
  user: ReturnType<typeof userEvent.setup>,
  targetName: string,
  pin: string,
) {
  await user.click(screen.getByTitle("Профил"));
  await user.click(screen.getByRole("menuitem", { name: "Смяна на потребител" }));
  await user.click(await screen.findByRole("button", { name: targetName }));
  for (const d of pin) {
    await user.click(screen.getByRole("button", { name: d }));
  }
  await user.click(screen.getByRole("button", { name: "Потвърди" }));
}

describe("AppShell: current-user UI reflects a PIN switch immediately", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
  });

  it("updates the header name right after switching, with no full page reload", async () => {
    renderShell();
    const user = userEvent.setup();

    // findBy, not getBy: the route itself renders regardless of auth state
    // (no RequireAuth in this harness), but the account button only
    // appears once the /auth/me fetch has actually resolved.
    expect(await screen.findByTitle("Профил")).toHaveTextContent("Мария");

    await switchViaAccountMenu(user, "Иво", "1234");

    // jsdom's window.location.reload isn't redefinable for a direct spy in
    // this environment; a real reload would tear down the whole React
    // tree/JS realm mid-test, so the header re-rendering with the new name
    // in this SAME render (no remount, no lost mocks/handlers) is itself
    // the proof no navigation happened - see also the "switching back"
    // test below, which round-trips the identity twice in one render.
    await waitFor(() => expect(screen.getByTitle("Профил")).toHaveTextContent("Иво"));
    expect(screen.getByTitle("Профил")).not.toHaveTextContent("Мария");
  });

  it("the me query cache reflects the new user right after a successful switch", async () => {
    const { queryClient } = renderShell();
    const user = userEvent.setup();

    await screen.findByTitle("Профил");
    await switchViaAccountMenu(user, "Иво", "1234");

    await waitFor(() => expect(queryClient.getQueryData(queryKeys.me)).toEqual(WORKER));
  });

  it("updates the owner/worker indicator (Настройки nav visibility) after switching to a non-owner", async () => {
    renderShell();
    const user = userEvent.setup();

    await screen.findByTitle("Профил");
    expect(screen.getByRole("link", { name: "Настройки" })).toBeInTheDocument();

    await switchViaAccountMenu(user, "Иво", "1234");

    await waitFor(() => expect(screen.getByTitle("Профил")).toHaveTextContent("Иво"));
    // Worker (is_owner: false) sees Настройки greyed - a real <span>, not a link.
    expect(screen.queryByRole("link", { name: "Настройки" })).not.toBeInTheDocument();
  });

  it("switching back to the original user updates the header again", async () => {
    renderShell();
    const user = userEvent.setup();

    await screen.findByTitle("Профил");
    await switchViaAccountMenu(user, "Иво", "1234");
    await waitFor(() => expect(screen.getByTitle("Профил")).toHaveTextContent("Иво"));

    // Self-exclusion in the picker (u.id !== me.user_id) only lists "Мария"
    // now if `me` genuinely updated - a stale `me` would still exclude the
    // old self and incorrectly offer "Иво" (the new self) as pickable.
    await switchViaAccountMenu(user, "Мария", "1234");

    await waitFor(() => expect(screen.getByTitle("Профил")).toHaveTextContent("Мария"));
    expect(screen.getByTitle("Профил")).not.toHaveTextContent("Иво");
  });

  it("logout still works after a prior PIN switch", async () => {
    renderShell();
    const user = userEvent.setup();

    await screen.findByTitle("Профил");
    await switchViaAccountMenu(user, "Иво", "1234");
    await waitFor(() => expect(screen.getByTitle("Профил")).toHaveTextContent("Иво"));

    await user.click(screen.getByText("Изход"));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/auth/logout"));
    expect(await screen.findByText("LOGIN_PAGE")).toBeInTheDocument();
  });

  it("manual lock still works after a prior PIN switch, and LockedPanel lists the current identity correctly", async () => {
    renderShell();
    const user = userEvent.setup();

    await screen.findByTitle("Профил");
    await switchViaAccountMenu(user, "Иво", "1234");
    await waitFor(() => expect(screen.getByTitle("Профил")).toHaveTextContent("Иво"));

    await user.click(screen.getByTitle("Профил"));
    await user.click(screen.getByRole("menuitem", { name: "Заключи екрана" }));

    expect(await screen.findByText("Екранът е заключен")).toBeInTheDocument();
    // "(вие)" self-suffix must land on "Иво" (the now-current user), not
    // the pre-switch "Мария" - proves LockedPanel's own `me` is in sync too.
    expect(await screen.findByRole("button", { name: "Иво (вие)" })).toBeInTheDocument();
  });
});
