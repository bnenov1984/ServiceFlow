import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { ApiError } from "../lib/api";
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

const ME = {
  user_id: "u1", name: "Мария", email: "m@m.bg", is_owner: true, language: "bg",
  company_id: "c1", csrf_token: "csrf-token-abc", active_modules: ["repairflow"],
  seat_limit: null, seat_usage: 1,
};

// Renders through the real AuthProvider (unlike AppShell.test.tsx's mocked
// useAuth) so the actual logout() implementation - the POST, the CSRF
// header, and the cache clear - runs for real, not a vi.fn() stand-in.
function renderShellWithRealAuth(logoutSucceeds = true) {
  // Mutable, not a fixed resolved value: logout() resets the "me" query in
  // place (queryClient.resetQueries), which triggers a real refetch of
  // /auth/me for the still-mounted AuthProvider observer - a mock that
  // always resolved ME regardless of logout would make that refetch
  // silently "re-login" the user, masking the very behavior under test.
  let loggedIn = true;
  mockGet.mockImplementation((path: string) => {
    if (path === "/auth/me") {
      return loggedIn ? Promise.resolve(ME)
        : Promise.reject(new ApiError(401, "not_authenticated", "errors.auth.required"));
    }
    if (path === "/platform/health") return Promise.resolve({ status: "ok" });
    return Promise.reject(new Error(`unexpected GET ${path}`));
  });
  mockPost.mockImplementation((path: string) => {
    if (path === "/auth/logout") {
      if (!logoutSucceeds) return Promise.reject(new Error("network error"));
      loggedIn = false;
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

describe("AppShell: tenant logout", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("clicking \"Изход\" sends POST /auth/logout, clears the session, and redirects to /login", async () => {
    const { queryClient } = renderShellWithRealAuth();
    const user = userEvent.setup();

    await screen.findByText("REPAIRFLOW_DASHBOARD");
    await user.click(screen.getByText("Изход"));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/auth/logout"));
    expect(await screen.findByText("LOGIN_PAGE")).toBeInTheDocument();
    expect(queryClient.getQueryData(queryKeys.me)).toBeUndefined();
  });

  it("clears the remembered app preference (shell/lastApp.ts) on logout", async () => {
    sessionStorage.setItem("bos.lastApp", "propertyflow");
    renderShellWithRealAuth();
    const user = userEvent.setup();

    await screen.findByText("REPAIRFLOW_DASHBOARD");
    await user.click(screen.getByText("Изход"));

    await screen.findByText("LOGIN_PAGE");
    expect(sessionStorage.getItem("bos.lastApp")).toBeNull();
  });

  it("still redirects to /login even if the backend logout call fails", async () => {
    // Regression test for the actual reported bug: AppShell's onClick was
    // `logout().then(() => navigate(...))` with no .catch/.finally - a
    // rejected logout() (any reason: CSRF mismatch, network error, session
    // already expired) silently swallowed the redirect and the button
    // appeared to "do nothing". logout() must always leave the user at
    // /login regardless of whether the server round-trip succeeded.
    renderShellWithRealAuth(false);
    const user = userEvent.setup();

    await screen.findByText("REPAIRFLOW_DASHBOARD");
    await user.click(screen.getByText("Изход"));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/auth/logout"));
    expect(await screen.findByText("LOGIN_PAGE")).toBeInTheDocument();
  });
});
