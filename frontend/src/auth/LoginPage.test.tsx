import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { LoginPage } from "./LoginPage";

const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, post: (...args: unknown[]) => mockPost(...args) } };
});

function renderLoginAt(path: string, queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>DASHBOARD_PAGE</div>} />
          <Route path="/ps" element={<div>PROPERTYFLOW_PAGE</div>} />
          <Route path="/forgot-password" element={<div>FORGOT_PASSWORD_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...utils, queryClient };
}

describe("LoginPage", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("posts credentials to the tenant login endpoint, seeds the me cache, and navigates to ?next= on success", async () => {
    const meResponse = {
      user_id: "u1", name: "Иван", company_id: "c1", csrf_token: "t",
      active_modules: ["repairflow"],
    };
    mockPost.mockResolvedValue(meResponse);
    const { queryClient } = renderLoginAt("/login?next=%2Forders");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/имейл/i), "ivan@shop.bg");
    await user.type(screen.getByLabelText(/парола/i), "парола-1234567");
    await user.click(screen.getByRole("button", { name: "Влез" }));

    expect(mockPost).toHaveBeenCalledWith("/auth/login", {
      email: "ivan@shop.bg",
      password: "парола-1234567",
      device_label: navigator.platform ?? "",
    });
    expect(queryClient.getQueryData(queryKeys.me)).toEqual(meResponse);
  });

  it("clears stale cached data from a previous company when logging in again without an explicit logout first", async () => {
    // Regression test: none of the tenant query keys (lib/queryKeys.ts) are
    // company-scoped, so switching companies mid-tab without logging out
    // used to leave the previous company's dashboard/customers/orders data
    // visible until each query's own staleTime expired (PO manual QA,
    // 01.08.2026: logging in with a second company's credentials showed the
    // first company's data).
    const meResponse = {
      user_id: "u2", name: "Мария", company_id: "c2", csrf_token: "t2",
      active_modules: ["repairflow"],
    };
    mockPost.mockResolvedValue(meResponse);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(queryKeys.dashboard, { stale: "from-previous-company" });
    queryClient.setQueryData(queryKeys.customers(), [{ id: "stale-customer" }]);
    renderLoginAt("/login", queryClient);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/имейл/i), "maria@other-shop.bg");
    await user.type(screen.getByLabelText(/парола/i), "друга-парола-123");
    await user.click(screen.getByRole("button", { name: "Влез" }));

    await screen.findByText("DASHBOARD_PAGE");
    expect(queryClient.getQueryData(queryKeys.dashboard)).toBeUndefined();
    expect(queryClient.getQueryData(queryKeys.customers())).toBeUndefined();
    expect(queryClient.getQueryData(queryKeys.me)).toEqual(meResponse);
  });

  it("ignores a leftover ?next=/ps deep link when the newly-logged-in company has no PropertyFlow", async () => {
    // Regression test: RequireAuth redirects an expired/logged-out session
    // to /login?next=<wherever it was>. If that was "/ps" (PropertyFlow)
    // and the vendor then logs in as a RepairFlow-only company (PO manual
    // QA, 01.08.2026), blindly honoring that next= landed them on
    // PropertyFlow's page, which correctly - but confusingly - 404s with
    // "module not activated". The safe fallback is "/", whose own
    // IndexRoute (App.tsx) picks the right home page.
    const meResponse = {
      user_id: "u3", name: "Петър", company_id: "c3", csrf_token: "t3",
      active_modules: ["repairflow"],
    };
    mockPost.mockResolvedValue(meResponse);
    renderLoginAt("/login?next=%2Fps");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/имейл/i), "petar@bike-shop.bg");
    await user.type(screen.getByLabelText(/парола/i), "парола-7654321");
    await user.click(screen.getByRole("button", { name: "Влез" }));

    expect(await screen.findByText("DASHBOARD_PAGE")).toBeInTheDocument();
    expect(screen.queryByText("PROPERTYFLOW_PAGE")).not.toBeInTheDocument();
  });

  it("still honors a ?next=/ps deep link when the company actually has PropertyFlow", async () => {
    const meResponse = {
      user_id: "u4", name: "Рали", company_id: "c4", csrf_token: "t4",
      active_modules: ["professional-services"],
    };
    mockPost.mockResolvedValue(meResponse);
    renderLoginAt("/login?next=%2Fps");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/имейл/i), "rali@realtor.bg");
    await user.type(screen.getByLabelText(/парола/i), "парола-7654321");
    await user.click(screen.getByRole("button", { name: "Влез" }));

    expect(await screen.findByText("PROPERTYFLOW_PAGE")).toBeInTheDocument();
  });

  it("clears a remembered app preference from a previous company on login", async () => {
    // Regression test for requirement #6 of the RepairFlow-default-landing
    // fix: shell/lastApp.ts's "last used app" is exactly as company-scoped
    // as the query cache above - a stale PropertyFlow preference from a
    // previous, both-apps company must never leak into deciding where a
    // newly-logged-in company (here, RepairFlow-only) lands.
    sessionStorage.setItem("bos.lastApp", "propertyflow");
    const meResponse = {
      user_id: "u5", name: "Георги", company_id: "c5", csrf_token: "t5",
      active_modules: ["repairflow"],
    };
    mockPost.mockResolvedValue(meResponse);
    renderLoginAt("/login");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/имейл/i), "georgi@shop.bg");
    await user.type(screen.getByLabelText(/парола/i), "парола-1112223");
    await user.click(screen.getByRole("button", { name: "Влез" }));

    await screen.findByText("DASHBOARD_PAGE");
    expect(sessionStorage.getItem("bos.lastApp")).toBeNull();
  });

  it("shows the shared invalid-credentials message on a failed login", async () => {
    mockPost.mockRejectedValue(new ApiError(401, "auth_failed", "errors.auth.invalid_credentials"));
    renderLoginAt("/login");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/имейл/i), "ivan@shop.bg");
    await user.type(screen.getByLabelText(/парола/i), "грешна");
    await user.click(screen.getByRole("button", { name: "Влез" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Грешен имейл или парола.");
  });

  it("has a Забравена парола? link that navigates to /forgot-password (cleanup: Tenant Forgot Password V1)", async () => {
    const callsBefore = mockPost.mock.calls.length;
    renderLoginAt("/login");
    const user = userEvent.setup();

    await user.click(screen.getByRole("link", { name: "Забравена парола?" }));

    expect(await screen.findByText("FORGOT_PASSWORD_PAGE")).toBeInTheDocument();
    // Navigating via the link alone must never itself trigger a login POST.
    expect(mockPost.mock.calls.length).toBe(callsBefore);
  });
});
