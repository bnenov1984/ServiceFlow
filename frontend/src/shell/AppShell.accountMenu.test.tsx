import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";

const mockGet = vi.fn();
const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      get: (...args: unknown[]) => mockGet(...args),
      post: (...args: unknown[]) => mockPost(...args),
    },
  };
});

const mockRefresh = vi.fn();
const mockLogout = vi.fn();
const mockUseAuth = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

function me(hasPin: boolean) {
  return {
    user_id: "u1", name: "Мария", email: "m@m.bg", is_owner: true, language: "bg",
    company_id: "c1", csrf_token: "t", active_modules: ["repairflow"],
    seat_limit: null, seat_usage: 1, has_pin: hasPin,
  };
}

function renderShell(hasPin: boolean) {
  mockUseAuth.mockReturnValue({ me: me(hasPin), isLoading: false, refresh: mockRefresh, logout: mockLogout });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<div>REPAIRFLOW_DASHBOARD</div>} />
          </Route>
          <Route path="/login" element={<div>LOGIN_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function openMenu(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByTitle("Профил"));
}

describe("AppShell: account menu", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockRefresh.mockReset();
    mockLogout.mockReset();
    mockLogout.mockResolvedValue(undefined);
    // Not under test here - PinSetupPrompt's own always-mounted Dialog+
    // SetPinForm (pre-existing, same idiom as PinSwitchDialog) would
    // otherwise render a second "Нов PIN" whenever has_pin is false.
    localStorage.clear();
    localStorage.setItem("bos.pinPromptDismissed.u1", "1");
    mockGet.mockImplementation((path: string) => {
      if (path === "/platform/health") return Promise.resolve({ status: "ok" });
      if (path === "/users") {
        return Promise.resolve([
          { id: "u1", name: "Мария", is_owner: true, is_active: true, has_pin: true },
        ]);
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
  });

  it("opens on click, lists the account actions, and closes after picking one", async () => {
    renderShell(true);
    const user = userEvent.setup();

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    await openMenu(user);
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Смени PIN" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Смяна на потребител" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Заключи екрана" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Изход" })).toBeInTheDocument();

    await user.click(screen.getByRole("menuitem", { name: "Изход" }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("labels the PIN item 'Задайте PIN' when has_pin is false, 'Смени PIN' when true", async () => {
    const { unmount } = renderShell(false);
    const user1 = userEvent.setup();
    await openMenu(user1);
    expect(screen.getByRole("menuitem", { name: "Задайте PIN" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Смени PIN" })).not.toBeInTheDocument();
    unmount();

    renderShell(true);
    const user2 = userEvent.setup();
    await openMenu(user2);
    expect(screen.getByRole("menuitem", { name: "Смени PIN" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Задайте PIN" })).not.toBeInTheDocument();
  });

  it("sets a PIN via the menu's SetPinForm dialog (reuses POST /auth/pin, no duplicated logic)", async () => {
    mockPost.mockImplementation((path: string) => {
      if (path === "/auth/pin") return Promise.resolve({ has_pin: true });
      return Promise.reject(new Error(`unexpected POST ${path}`));
    });
    renderShell(false);
    const user = userEvent.setup();
    await openMenu(user);
    await user.click(screen.getByRole("menuitem", { name: "Задайте PIN" }));

    expect(await screen.findByText("Нов PIN")).toBeInTheDocument();
    for (const d of "1234") await user.click(screen.getByRole("button", { name: d }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));
    for (const d of "1234") await user.click(screen.getByRole("button", { name: d }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/auth/pin", { pin: "1234" }));
    await waitFor(() => expect(mockRefresh).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByText("Нов PIN")).not.toBeInTheDocument());
  });

  it("locks the screen immediately via 'Заключи екрана', reusing LockedPanel/the idle-timeout overlay", async () => {
    renderShell(true);
    const user = userEvent.setup();

    expect(screen.queryByText("Екранът е заключен")).not.toBeInTheDocument();
    await openMenu(user);
    await user.click(screen.getByRole("menuitem", { name: "Заключи екрана" }));

    expect(await screen.findByText("Екранът е заключен")).toBeInTheDocument();
    // The "(вие)" self-suffix disambiguates the LockedPanel's user-list entry
    // from the still-present (but not interactive under the overlay) header
    // account button, which also renders the plain name "Мария".
    expect(await screen.findByRole("button", { name: "Мария (вие)" })).toBeInTheDocument();
  });

  it("unlocks after the correct PIN, same as an idle-triggered lock", async () => {
    mockPost.mockImplementation((path: string) => {
      if (path === "/auth/pin-switch") return Promise.resolve({ name: "Мария" });
      return Promise.reject(new Error(`unexpected POST ${path}`));
    });
    renderShell(true);
    const user = userEvent.setup();
    await openMenu(user);
    await user.click(screen.getByRole("menuitem", { name: "Заключи екрана" }));

    await user.click(await screen.findByRole("button", { name: "Мария (вие)" }));
    for (const d of "1234") await user.click(screen.getByRole("button", { name: d }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith(
      "/auth/pin-switch", { user_id: "u1", pin: "1234" },
    ));
    await waitFor(() => expect(screen.queryByText("Екранът е заключен")).not.toBeInTheDocument());
  });

  it("logs out from the menu and redirects to /login", async () => {
    mockLogout.mockImplementation(async () => {
      await mockPost("/auth/logout");
    });
    mockPost.mockImplementation((path: string) => {
      if (path === "/auth/logout") return Promise.resolve({ ok: true });
      return Promise.reject(new Error(`unexpected POST ${path}`));
    });
    renderShell(true);
    const user = userEvent.setup();
    await openMenu(user);
    await user.click(screen.getByRole("menuitem", { name: "Изход" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/auth/logout"));
    expect(await screen.findByText("LOGIN_PAGE")).toBeInTheDocument();
  });
});
