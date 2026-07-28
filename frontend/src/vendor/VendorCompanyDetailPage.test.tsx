import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { VendorCompanyDetailPage } from "./VendorCompanyDetailPage";

const mockGet = vi.fn();
const mockPut = vi.fn();
const mockDelete = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      get: (...args: unknown[]) => mockGet(...args),
      put: (...args: unknown[]) => mockPut(...args),
      delete: (...args: unknown[]) => mockDelete(...args),
    },
  };
});

function renderPage(id = "c1", queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/vendor/companies/${id}`]}>
        <Routes>
          <Route path="/vendor/companies" element={<div>COMPANIES_LIST_PAGE</div>} />
          <Route path="/vendor/companies/:id" element={<VendorCompanyDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

const BASE_COMPANY = {
  id: "c1", name: "Сервиз А", business_profile: "generic_repair",
  subscription_state: "trial", trial_ends_at: null, seat_limit: null,
  seat_usage: 1, created_at: "2026-07-01T00:00:00Z",
  subscription_state_changed_at: "2026-07-01T00:00:00Z",
};

describe("VendorCompanyDetailPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPut.mockReset();
    mockDelete.mockReset();
  });

  it("shows loading skeletons while the company is fetching", () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(document.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("shows a not-found state (with a back link) for a 404", async () => {
    mockGet.mockRejectedValue(
      new ApiError(404, "company_not_found", "errors.provisioning.company_not_found"),
    );
    renderPage();
    expect(await screen.findByText("Няма такава компания.")).toBeInTheDocument();
    expect(screen.getByText("← Компании")).toBeInTheDocument();
  });

  it("shows a generic error state with retry for a non-404 failure", async () => {
    mockGet.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    renderPage();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("renders the full field set for a normal detail response", async () => {
    mockGet.mockResolvedValue({
      id: "c1", name: "Сервиз А", business_profile: "generic_repair",
      active_modules: ["professional-services"], subscription_state: "active",
      trial_ends_at: null, seat_limit: null, seat_usage: 3,
      created_at: "2026-07-01T00:00:00Z", subscription_state_changed_at: "2026-07-15T00:00:00Z",
    });
    renderPage();

    expect(await screen.findByText("Сервиз А")).toBeInTheDocument();
    expect(screen.getByText("generic_repair")).toBeInTheDocument();
    expect(screen.getByText("professional-services")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("3/неограничено")).toBeInTheDocument();
    expect(screen.queryByText("Пробният период приключва на")).not.toBeInTheDocument();
  });

  it("shows the trial end date when present", async () => {
    mockGet.mockResolvedValue({
      id: "c1", name: "Сервиз Б", business_profile: "generic_repair",
      active_modules: [], subscription_state: "trial",
      trial_ends_at: "2026-08-11T14:43:05.383874Z", seat_limit: null, seat_usage: 1,
      created_at: "2026-07-01T00:00:00Z", subscription_state_changed_at: "2026-07-01T00:00:00Z",
    });
    renderPage();

    expect(await screen.findByText("Пробният период приключва на")).toBeInTheDocument();
    expect(screen.getByText("2026-08-11T14:43:05.383874Z")).toBeInTheDocument();
  });

  it("grants the module directly and updates the displayed set with no extra GET", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [] });
    mockPut.mockResolvedValue({
      company_id: "c1", module_key: "professional-services",
      active_modules: ["professional-services"], changed: true, audit_id: "a1",
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Активирай PropertyFlow" }));

    expect(await screen.findByText("professional-services")).toBeInTheDocument();
    expect(mockPut).toHaveBeenCalledWith("/platform-admin/companies/c1/modules/professional-services");
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it("opens a confirm dialog before revoking, without calling the API yet", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: ["professional-services"] });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Деактивирай PropertyFlow" }));

    expect(screen.getByText("Сигурни ли сте, че искате да деактивирате PropertyFlow за тази компания?"))
      .toBeInTheDocument();
    expect(mockDelete).not.toHaveBeenCalled();
  });

  it("makes no API call when the revoke confirmation is cancelled", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: ["professional-services"] });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Деактивирай PropertyFlow" }));
    await user.click(screen.getByRole("button", { name: "Отказ" }));

    expect(mockDelete).not.toHaveBeenCalled();
    expect(document.querySelector("dialog")).not.toHaveAttribute("open");
  });

  it("revokes on confirmation, calling DELETE on the exact expected path", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: ["professional-services"] });
    mockDelete.mockResolvedValue({
      company_id: "c1", module_key: "professional-services",
      active_modules: [], changed: true, audit_id: "a2",
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Деактивирай PropertyFlow" }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith(
      "/platform-admin/companies/c1/modules/professional-services",
    ));
    expect(await screen.findByText("Няма активирани приложения")).toBeInTheDocument();
  });

  it("shows a recoverable inline error on failure, leaving the rest of the page intact", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [] });
    mockPut.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Активирай PropertyFlow" }));

    expect(await screen.findByText("Възникна неочаквана грешка. Опитайте отново.")).toBeInTheDocument();
    expect(screen.getByText("Сервиз А")).toBeInTheDocument();
    expect(screen.getByText("generic_repair")).toBeInTheDocument();
  });

  it("invalidates [\"vendor\",\"companies\"] on a successful grant", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [] });
    mockPut.mockResolvedValue({
      company_id: "c1", module_key: "professional-services",
      active_modules: ["professional-services"], changed: true, audit_id: "a1",
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["vendor", "companies"], [{ id: "c1" }]);
    renderPage("c1", queryClient);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Активирай PropertyFlow" }));

    await waitFor(() =>
      expect(queryClient.getQueryState(["vendor", "companies"])?.isInvalidated).toBe(true));
  });

  it("prevents a duplicate grant request from a rapid double-click", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [] });
    let resolvePut: (v: unknown) => void = () => {};
    mockPut.mockReturnValue(new Promise((resolve) => { resolvePut = resolve; }));
    renderPage();
    const user = userEvent.setup();

    const button = await screen.findByRole("button", { name: "Активирай PropertyFlow" });
    await user.click(button);
    await user.click(button);

    resolvePut({
      company_id: "c1", module_key: "professional-services",
      active_modules: ["professional-services"], changed: true, audit_id: "a1",
    });
    await waitFor(() => expect(mockPut).toHaveBeenCalledTimes(1));
  });
});
