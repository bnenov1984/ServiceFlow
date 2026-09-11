import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { VendorCompanyDetailPage } from "./VendorCompanyDetailPage";

const mockGet = vi.fn();
const mockPut = vi.fn();
const mockDelete = vi.fn();
const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      get: (...args: unknown[]) => mockGet(...args),
      put: (...args: unknown[]) => mockPut(...args),
      delete: (...args: unknown[]) => mockDelete(...args),
      post: (...args: unknown[]) => mockPost(...args),
    },
  };
});

function transitionDialog(): HTMLElement {
  const found = [...document.querySelectorAll("dialog")].find(
    (d) => d.textContent?.includes("Промяна на статус на абонамента"),
  );
  if (!found) throw new Error("transition dialog not found in the DOM");
  return found as HTMLElement;
}

function seatLimitEditor(): HTMLElement {
  const input = document.getElementById("seat-limit-new");
  if (!input?.parentElement) throw new Error("seat limit editor not found in the DOM");
  return input.parentElement as HTMLElement;
}

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
  business_type_label: "Общ ремонт на техника",
  subscription_state: "trial", trial_ends_at: null, seat_limit: null,
  seat_usage: 1, created_at: "2026-07-01T00:00:00Z",
  subscription_state_changed_at: "2026-07-01T00:00:00Z",
};

describe("VendorCompanyDetailPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPut.mockReset();
    mockDelete.mockReset();
    mockPost.mockReset();
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
      business_type_label: "Общ ремонт на техника",
      active_modules: ["professional-services"], subscription_state: "active",
      trial_ends_at: null, seat_limit: null, seat_usage: 3,
      created_at: "2026-07-01T00:00:00Z", subscription_state_changed_at: "2026-07-15T00:00:00Z",
    });
    renderPage();

    expect(await screen.findByText("Сервиз А")).toBeInTheDocument();
    expect(screen.getByText("generic_repair")).toBeInTheDocument();
    expect(screen.getByText("Общ ремонт на техника")).toBeInTheDocument();
    expect(screen.getByText("PropertyFlow")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("3/неограничено")).toBeInTheDocument();
    expect(screen.queryByText("Пробният период приключва на")).not.toBeInTheDocument();
  });

  it("hides the grant button and explains why when a different module is already active", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: ["repairflow"] });
    renderPage();

    expect(await screen.findByText(
      "Компанията вече ползва друго приложение. Деактивирайте го, за да превключите.",
    )).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Активирай PropertyFlow" })).not.toBeInTheDocument();
  });

  it("shows the trial end date when present", async () => {
    mockGet.mockResolvedValue({
      id: "c1", name: "Сервиз Б", business_profile: "generic_repair",
      business_type_label: "Общ ремонт на техника",
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

    expect(await screen.findByText("PropertyFlow")).toBeInTheDocument();
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

  it("always shows the subscription transition button", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [] });
    renderPage();

    expect(await screen.findByRole("button", { name: "Промени статус" })).toBeInTheDocument();
  });

  it("opens the transition dialog with all 5 states and the current state pre-selected; confirm starts disabled", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], subscription_state: "trial" });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени статус" }));

    const select = screen.getByLabelText("Нов статус") as HTMLSelectElement;
    expect(select.value).toBe("trial");
    expect(["trial", "active", "grace_period", "suspended", "cancelled"]).toEqual(
      [...select.options].map((o) => o.value),
    );
    expect(screen.getByRole("button", { name: "Потвърди" })).toBeDisabled();
  });

  it("enables confirm once a reason is typed, and submits the exact expected payload", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], subscription_state: "trial" });
    mockPost.mockResolvedValue({
      company_id: "c1", old_state: "trial", new_state: "suspended",
      reason: "Неплатена фактура", audit_id: "a3",
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени статус" }));
    await user.selectOptions(screen.getByLabelText("Нов статус"), "suspended");
    await user.type(screen.getByLabelText("Причина"), "Неплатена фактура");
    const confirmButton = screen.getByRole("button", { name: "Потвърди" });
    expect(confirmButton).not.toBeDisabled();
    await user.click(confirmButton);

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith(
      "/platform-admin/companies/c1/subscription/transitions",
      { new_state: "suspended", reason: "Неплатена фактура" },
    ));
  });

  it("invalidates both the company and companies list queries on success, and closes the dialog", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], subscription_state: "trial" });
    mockPost.mockResolvedValue({
      company_id: "c1", old_state: "trial", new_state: "suspended",
      reason: "test", audit_id: "a3",
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["vendor", "companies"], [{ id: "c1" }]);
    renderPage("c1", queryClient);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени статус" }));
    await user.type(screen.getByLabelText("Причина"), "test");
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    // The detail query has an active observer, so invalidation triggers an
    // immediate refetch (a second GET) rather than leaving isInvalidated set.
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2));
    expect(queryClient.getQueryState(["vendor", "companies"])?.isInvalidated).toBe(true);
    expect(transitionDialog()).not.toHaveAttribute("open");
  });

  it("cancel closes the transition dialog without calling the API", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], subscription_state: "trial" });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени статус" }));
    await user.type(screen.getByLabelText("Причина"), "test");
    await user.click(screen.getByRole("button", { name: "Отказ" }));

    expect(mockPost).not.toHaveBeenCalled();
    expect(transitionDialog()).not.toHaveAttribute("open");
  });

  it("allows re-submitting the same state the company is already in", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], subscription_state: "active" });
    mockPost.mockResolvedValue({
      company_id: "c1", old_state: "active", new_state: "active",
      reason: "reconfirmed", audit_id: "a4",
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени статус" }));
    await user.type(screen.getByLabelText("Причина"), "reconfirmed");
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith(
      "/platform-admin/companies/c1/subscription/transitions",
      { new_state: "active", reason: "reconfirmed" },
    ));
  });

  it("shows a recoverable inline error on failure and keeps the dialog open with the reason intact", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], subscription_state: "trial" });
    mockPost.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени статус" }));
    await user.type(screen.getByLabelText("Причина"), "test reason");
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    expect(await screen.findByText("Възникна неочаквана грешка. Опитайте отново.")).toBeInTheDocument();
    expect(transitionDialog()).toHaveAttribute("open");
    expect(screen.getByLabelText("Причина")).toHaveValue("test reason");
  });

  it("prevents a duplicate transition request from a rapid double-click", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], subscription_state: "trial" });
    let resolvePost: (v: unknown) => void = () => {};
    mockPost.mockReturnValue(new Promise((resolve) => { resolvePost = resolve; }));
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени статус" }));
    await user.type(screen.getByLabelText("Причина"), "test");
    const confirmButton = screen.getByRole("button", { name: "Потвърди" });
    await user.click(confirmButton);
    await user.click(confirmButton);

    resolvePost({
      company_id: "c1", old_state: "trial", new_state: "trial",
      reason: "test", audit_id: "a5",
    });
    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
  });

  it("pre-fills the current numeric seat limit with the unlimited checkbox unchecked", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], seat_limit: 5 });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени" }));

    expect(screen.getByLabelText("Нов лимит на местата")).toHaveValue(5);
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });

  it("shows the unlimited checkbox checked and the input disabled when seat_limit is null", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], seat_limit: null });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени" }));

    expect(screen.getByRole("checkbox")).toBeChecked();
    expect(screen.getByLabelText("Нов лимит на местата")).toBeDisabled();
  });

  it("submits a new numeric seat limit on the exact expected path", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], seat_limit: 3 });
    mockPut.mockResolvedValue({ company_id: "c1", seat_limit: 8, changed: true, audit_id: "s1" });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени" }));
    const input = screen.getByLabelText("Нов лимит на местата");
    await user.clear(input);
    await user.type(input, "8");
    await user.click(within(seatLimitEditor()).getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockPut).toHaveBeenCalledWith(
      "/platform-admin/companies/c1/seat-limit", { seat_limit: 8 },
    ));
  });

  it("submits null when the unlimited checkbox is checked", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], seat_limit: 5 });
    mockPut.mockResolvedValue({ company_id: "c1", seat_limit: null, changed: true, audit_id: "s2" });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени" }));
    await user.click(screen.getByRole("checkbox"));
    await user.click(within(seatLimitEditor()).getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockPut).toHaveBeenCalledWith(
      "/platform-admin/companies/c1/seat-limit", { seat_limit: null },
    ));
  });

  it("invalidates both the company and companies list queries on a successful seat limit change", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], seat_limit: 3 });
    mockPut.mockResolvedValue({ company_id: "c1", seat_limit: 8, changed: true, audit_id: "s1" });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["vendor", "companies"], [{ id: "c1" }]);
    renderPage("c1", queryClient);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени" }));
    const input = screen.getByLabelText("Нов лимит на местата");
    await user.clear(input);
    await user.type(input, "8");
    await user.click(within(seatLimitEditor()).getByRole("button", { name: "Потвърди" }));

    await waitFor(() => {
      expect(queryClient.getQueryState(["vendor", "companies"])?.isInvalidated).toBe(true);
    });
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2));
  });

  it("shows a recoverable inline error on failure, leaving the editor open", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], seat_limit: 3 });
    mockPut.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени" }));
    const input = screen.getByLabelText("Нов лимит на местата");
    await user.clear(input);
    await user.type(input, "8");
    await user.click(within(seatLimitEditor()).getByRole("button", { name: "Потвърди" }));

    expect(await screen.findByText("Възникна неочаквана грешка. Опитайте отново.")).toBeInTheDocument();
    expect(screen.getByLabelText("Нов лимит на местата")).toHaveValue(8);
  });

  it("prevents a duplicate seat limit request from a rapid double-click", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], seat_limit: 3 });
    let resolvePut: (v: unknown) => void = () => {};
    mockPut.mockReturnValue(new Promise((resolve) => { resolvePut = resolve; }));
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Промени" }));
    const input = screen.getByLabelText("Нов лимит на местата");
    await user.clear(input);
    await user.type(input, "8");
    const confirmButton = within(seatLimitEditor()).getByRole("button", { name: "Потвърди" });
    await user.click(confirmButton);
    await user.click(confirmButton);

    resolvePut({ company_id: "c1", seat_limit: 8, changed: true, audit_id: "s1" });
    await waitFor(() => expect(mockPut).toHaveBeenCalledTimes(1));
  });

  it("shows the archive button (never restore) for an active company", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], archived_at: null });
    renderPage();

    expect(await screen.findByRole("button", { name: "Архивирай" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Възстанови" })).not.toBeInTheDocument();
    expect(screen.queryByText("Архивирана")).not.toBeInTheDocument();
  });

  it("opens a confirm dialog before archiving, without calling the API yet", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], archived_at: null });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Архивирай" }));

    expect(screen.getByText(
      "Сигурни ли сте, че искате да архивирате тази компания? Потребителите ѝ няма да могат да влизат, докато не бъде възстановена. Нищо не се изтрива.",
    )).toBeInTheDocument();
    expect(mockPut).not.toHaveBeenCalled();
  });

  it("archives on confirmation, updates the badge and archived-at field with no extra GET", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], archived_at: null });
    mockPut.mockResolvedValue({ company_id: "c1", archived_at: "2026-08-03T12:00:00Z", changed: true, audit_id: "a9" });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Архивирай" }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockPut).toHaveBeenCalledWith("/platform-admin/companies/c1/archive"));
    expect(await screen.findByText("Архивирана")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Възстанови" })).toBeInTheDocument();
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it("restores an archived company directly, unconfirmed", async () => {
    mockGet.mockResolvedValue({
      ...BASE_COMPANY, active_modules: [], archived_at: "2026-08-01T00:00:00Z",
    });
    mockPut.mockResolvedValue({ company_id: "c1", archived_at: null, changed: true, audit_id: "a10" });
    renderPage();
    const user = userEvent.setup();

    expect(await screen.findByRole("button", { name: "Възстанови" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Възстанови" }));

    await waitFor(() => expect(mockPut).toHaveBeenCalledWith("/platform-admin/companies/c1/restore"));
    expect(screen.queryByText("Архивирана")).not.toBeInTheDocument();
  });

  it("cancelling the archive confirmation makes no API call", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], archived_at: null });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Архивирай" }));
    await user.click(screen.getByRole("button", { name: "Отказ" }));

    expect(mockPut).not.toHaveBeenCalled();
  });

  it("invalidates [\"vendor\",\"companies\"] on a successful archive", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], archived_at: null });
    mockPut.mockResolvedValue({ company_id: "c1", archived_at: "2026-08-03T12:00:00Z", changed: true, audit_id: "a9" });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["vendor", "companies"], [{ id: "c1" }]);
    renderPage("c1", queryClient);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Архивирай" }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    await waitFor(() =>
      expect(queryClient.getQueryState(["vendor", "companies"])?.isInvalidated).toBe(true));
  });

  it("shows a recoverable inline error on archive failure", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], archived_at: null });
    mockPut.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Архивирай" }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    expect(await screen.findByText("Възникна неочаквана грешка. Опитайте отново.")).toBeInTheDocument();
    expect(screen.getByText("Сервиз А")).toBeInTheDocument();
  });

  it("prevents a duplicate archive request from a rapid double-click", async () => {
    mockGet.mockResolvedValue({ ...BASE_COMPANY, active_modules: [], archived_at: null });
    let resolvePut: (v: unknown) => void = () => {};
    mockPut.mockReturnValue(new Promise((resolve) => { resolvePut = resolve; }));
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Архивирай" }));
    const confirmButton = screen.getByRole("button", { name: "Потвърди" });
    await user.click(confirmButton);
    await user.click(confirmButton);

    resolvePut({ company_id: "c1", archived_at: "2026-08-03T12:00:00Z", changed: true, audit_id: "a9" });
    await waitFor(() => expect(mockPut).toHaveBeenCalledTimes(1));
  });
});
