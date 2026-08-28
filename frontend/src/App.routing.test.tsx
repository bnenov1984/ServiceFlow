import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { ApiError } from "./lib/api";

const mockGet = vi.fn();
const mockPost = vi.fn();
vi.mock("./lib/api", async () => {
  const actual = await vi.importActual<typeof import("./lib/api")>("./lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      get: (...args: unknown[]) => mockGet(...args),
      post: (...args: unknown[]) => mockPost(...args),
    },
  };
});

function meFor(activeModules: string[], overrides: Partial<Record<string, unknown>> = {}) {
  return {
    user_id: "u1", name: "Иван", email: "ivan@shop.bg", is_owner: true, language: "bg",
    company_id: "c1", csrf_token: "t", active_modules: activeModules,
    seat_limit: null, seat_usage: 1, ...overrides,
  };
}

function stubDataEndpoints(getMe: () => ReturnType<typeof meFor> | null) {
  mockGet.mockImplementation((path: string) => {
    if (path === "/auth/me") {
      const me = getMe();
      return me ? Promise.resolve(me)
        : Promise.reject(new ApiError(401, "not_authenticated", "errors.auth.required"));
    }
    if (path === "/platform/health") return Promise.resolve({ status: "ok" });
    if (path.startsWith("/dashboard")) {
      return Promise.resolve({
        active_orders: 0, waiting_parts: 0, ready: { count: 0, over_limit: 0 },
        overdue: 0, today_tasks: 0, call_tasks: 0,
      });
    }
    if (path.startsWith("/ps/")) return Promise.resolve([]);
    if (path === "/users") return Promise.resolve([]);
    return Promise.reject(new Error(`unexpected GET ${path}`));
  });
}

function renderAppAt(path: string, activeModules: string[]) {
  stubDataEndpoints(() => meFor(activeModules));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("Tenant login landing route (App.tsx IndexRoute) — RepairFlow is not the default", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("RepairFlow-only lands on the RepairFlow dashboard", async () => {
    renderAppAt("/", ["repairflow"]);
    expect(await screen.findByRole("navigation", { name: /RepairFlow navigation/i })).toBeInTheDocument();
  });

  it("PropertyFlow-only lands on the PropertyFlow dashboard, not RepairFlow", async () => {
    renderAppAt("/", ["professional-services"]);
    expect(await screen.findByRole("navigation", { name: /PropertyFlow navigation/i })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: /RepairFlow navigation/i })).not.toBeInTheDocument();
  });

  it("both active with no remembered preference shows the app chooser, not RepairFlow by default", async () => {
    renderAppAt("/", ["repairflow", "professional-services"]);
    expect(await screen.findByText("Изберете приложение")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: /RepairFlow navigation/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: /PropertyFlow navigation/i })).not.toBeInTheDocument();
  });

  it("both active with a remembered PropertyFlow preference skips the chooser", async () => {
    sessionStorage.setItem("bos.lastApp", "propertyflow");
    renderAppAt("/", ["repairflow", "professional-services"]);
    expect(await screen.findByRole("navigation", { name: /PropertyFlow navigation/i })).toBeInTheDocument();
  });

  it("both active with a remembered RepairFlow preference lands on RepairFlow (by choice, not default)", async () => {
    sessionStorage.setItem("bos.lastApp", "repairflow");
    renderAppAt("/", ["repairflow", "professional-services"]);
    expect(await screen.findByRole("navigation", { name: /RepairFlow navigation/i })).toBeInTheDocument();
  });

  it("no active apps shows the neutral empty state, never RepairFlow's own chrome", async () => {
    renderAppAt("/", []);
    expect(await screen.findByText("Няма активирани приложения")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: /RepairFlow navigation/i })).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/Търсене/)).not.toBeInTheDocument();
    expect(screen.queryByText("+ Нова поръчка")).not.toBeInTheDocument();
  });

  it("a fresh login via the real form lands on the RepairFlow dashboard, not stuck back on /login", async () => {
    // Regression test for the TanStack Query notify-manager race: cache
    // writes (setQueryData) always defer their subscriber notification to a
    // macrotask, so navigating to "/" immediately after used to let
    // RequireAuth read a still-stale (empty) `me` and bounce back to
    // /login. See auth/LoginPage.tsx's onSubmit for the fix.
    let currentMe: ReturnType<typeof meFor> | null = null;
    stubDataEndpoints(() => currentMe);
    mockPost.mockImplementation((path: string) => {
      if (path === "/auth/login") {
        currentMe = meFor(["repairflow"]);
        return Promise.resolve(currentMe);
      }
      return Promise.reject(new Error(`unexpected POST ${path}`));
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={["/login"]}>
            <App />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    );
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText(/имейл/i), "a@b.bg");
    await user.type(screen.getByLabelText(/парола/i), "паролаааааа12");
    await user.click(screen.getByRole("button", { name: "Влез" }));

    expect(await screen.findByRole("navigation", { name: /RepairFlow navigation/i })).toBeInTheDocument();
  });

  it("logging out of a both-apps company (with a chosen preference) and into a RepairFlow-only company lands on RepairFlow, not the stale preference", async () => {
    let currentMe: ReturnType<typeof meFor> | null = meFor(["repairflow", "professional-services"]);
    stubDataEndpoints(() => currentMe);
    mockPost.mockImplementation((path: string) => {
      if (path === "/auth/logout") {
        currentMe = null;
        return Promise.resolve({ ok: true });
      }
      if (path === "/auth/login") {
        currentMe = meFor(["repairflow"], { user_id: "u2", name: "Нов", company_id: "c2" });
        return Promise.resolve(currentMe);
      }
      return Promise.reject(new Error(`unexpected POST ${path}`));
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={["/"]}>
            <App />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    );
    const user = userEvent.setup();

    // Company A (both apps): pick PropertyFlow, recording the preference.
    await screen.findByText("Изберете приложение");
    await user.click(screen.getByText("PropertyFlow"));
    await screen.findByRole("navigation", { name: /PropertyFlow navigation/i });
    expect(sessionStorage.getItem("bos.lastApp")).toBe("propertyflow");

    // Log out.
    await user.click(screen.getByText("Изход"));
    await screen.findByLabelText(/имейл/i);
    expect(sessionStorage.getItem("bos.lastApp")).toBeNull();

    // Log into company B (RepairFlow-only) - must land on RepairFlow, not
    // be silently affected by company A's stale PropertyFlow preference.
    await user.type(screen.getByLabelText(/имейл/i), "new@bike-shop.bg");
    await user.type(screen.getByLabelText(/парола/i), "нова-парола-123456");
    await user.click(screen.getByRole("button", { name: "Влез" }));

    expect(await screen.findByRole("navigation", { name: /RepairFlow navigation/i })).toBeInTheDocument();
  });
});

describe("Settings default section (Issue 37) — bare /settings lands on Employees", () => {
  it("redirects /settings to the employee list with the add-employee action visible", async () => {
    renderAppAt("/settings", ["repairflow"]);

    expect(await screen.findByRole("heading", { name: "Служители" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Добави служител" })).toBeInTheDocument();
  });
});
