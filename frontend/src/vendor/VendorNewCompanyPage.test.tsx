import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { RequireVendorAuth } from "./RequireVendorAuth";
import { VendorNewCompanyPage } from "./VendorNewCompanyPage";

const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, post: (...args: unknown[]) => mockPost(...args) } };
});

// Only consulted by the redirect test below, via RequireVendorAuth —
// VendorNewCompanyPage itself never calls useVendorAuth.
const mockUseVendorAuth = vi.fn();
vi.mock("./VendorAuthContext", () => ({
  useVendorAuth: () => mockUseVendorAuth(),
}));

function DetailPlaceholder() {
  const { id } = useParams<{ id: string }>();
  return <div>COMPANY_DETAIL_PAGE:{id}</div>;
}

function renderPage(queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/vendor/companies/new"]}>
        <Routes>
          <Route path="/vendor/companies/new" element={<VendorNewCompanyPage />} />
          <Route path="/vendor/companies/:id" element={<DetailPlaceholder />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Име на компанията"), "Нов Сервиз ЕООД");
  await user.type(screen.getByLabelText("Име на собственика"), "Иван Иванов");
  await user.type(screen.getByLabelText("Имейл"), "owner@dev-seed.bg");
  await user.type(screen.getByLabelText("Парола"), "дълга-парола-1234");
  await user.type(
    screen.getByLabelText("Описание на дейността"), "Сервиз за велосипеди и тротинетки",
  );
}

const SUCCESS_RESULT = {
  company_id: "c1", owner_id: "o1", subscription_state: "trial",
  trial_ends_at: "2026-08-11T00:00:00Z", business_profile: "generic_repair",
  business_type_label: "Сервиз за велосипеди и тротинетки",
  activated_modules: ["repairflow"], audit_id: "a1",
};

describe("VendorNewCompanyPage", () => {
  beforeEach(() => {
    mockPost.mockReset();
    mockUseVendorAuth.mockReset();
  });

  it("redirects to /vendor/login when there is no vendor session", () => {
    mockUseVendorAuth.mockReturnValue({ me: null, isLoading: false });
    render(
      <MemoryRouter initialEntries={["/vendor/companies/new"]}>
        <Routes>
          <Route path="/vendor/login" element={<div>VENDOR_LOGIN_PAGE</div>} />
          <Route
            path="/vendor/companies/new"
            element={<RequireVendorAuth><VendorNewCompanyPage /></RequireVendorAuth>}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("VENDOR_LOGIN_PAGE")).toBeInTheDocument();
  });

  it("renders every backend-supported field and no unsupported ones", () => {
    renderPage();
    expect(screen.getByLabelText("Име на компанията")).toBeInTheDocument();
    expect(screen.getByLabelText("Име на собственика")).toBeInTheDocument();
    expect(screen.getByLabelText("Имейл")).toBeInTheDocument();
    expect(screen.getByLabelText("Парола")).toBeInTheDocument();
    expect(screen.getByLabelText("Бизнес профил")).toBeInTheDocument();
    expect(screen.getByLabelText("Описание на дейността")).toBeInTheDocument();
    expect(screen.getByLabelText("RepairFlow")).toBeInTheDocument();
    expect(screen.getByLabelText("PropertyFlow")).toBeInTheDocument();
    // Not part of the ProvisionCompanyRequest contract — must never appear.
    expect(screen.queryByLabelText(/места|лимит|валута|часова зона|локал/i)).not.toBeInTheDocument();
  });

  it("renders both module radio options unselected by default — no application active by default", () => {
    renderPage();
    expect(screen.getByLabelText("RepairFlow")).not.toBeChecked();
    expect(screen.getByLabelText("PropertyFlow")).not.toBeChecked();
  });

  it("defaults the business profile field to \"Общ ремонт\", a fixed vocabulary select", () => {
    renderPage();
    expect(screen.getByLabelText("Бизнес профил")).toHaveValue("generic_repair");
  });

  it("maps every human-readable business-profile label to its canonical code", async () => {
    mockPost.mockResolvedValue(SUCCESS_RESULT);
    renderPage();
    const user = userEvent.setup();
    await fillRequiredFields(user);
    await user.click(screen.getByLabelText("RepairFlow"));

    await user.selectOptions(screen.getByLabelText("Бизнес профил"), "Авторемонт");
    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    expect(mockPost.mock.calls[0][1]).toMatchObject({ business_profile: "automotive_repair" });
  });

  it("blocks submission when the business type label is empty, with the exact required message", async () => {
    renderPage();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Име на компанията"), "Нов Сервиз ЕООД");
    await user.type(screen.getByLabelText("Име на собственика"), "Иван Иванов");
    await user.type(screen.getByLabelText("Имейл"), "owner@dev-seed.bg");
    await user.type(screen.getByLabelText("Парола"), "дълга-парола-1234");
    await user.click(screen.getByLabelText("RepairFlow"));
    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    expect(mockPost).not.toHaveBeenCalled();
    expect(await screen.findByText("Въведете описание на дейността.")).toBeInTheDocument();
  });

  it("sends the free-text business type label verbatim, trimmed", async () => {
    mockPost.mockResolvedValue(SUCCESS_RESULT);
    renderPage();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Име на компанията"), "Нов Сервиз ЕООД");
    await user.type(screen.getByLabelText("Име на собственика"), "Иван Иванов");
    await user.type(screen.getByLabelText("Имейл"), "owner@dev-seed.bg");
    await user.type(screen.getByLabelText("Парола"), "дълга-парола-1234");
    await user.type(screen.getByLabelText("Описание на дейността"), "  Ремонт на велосипеди  ");
    await user.click(screen.getByLabelText("RepairFlow"));
    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    expect(mockPost.mock.calls[0][1]).toMatchObject({ business_type_label: "Ремонт на велосипеди" });
  });

  it("blocks submission when required fields are empty", async () => {
    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    expect(mockPost).not.toHaveBeenCalled();
    expect(await screen.findAllByRole("alert")).not.toHaveLength(0);
  });

  it("blocks submission with the exact PO-specified message when no application is selected", async () => {
    renderPage();
    const user = userEvent.setup();
    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    expect(mockPost).not.toHaveBeenCalled();
    expect(await screen.findByText("Изберете поне едно приложение.")).toBeInTheDocument();
  });

  it("sends modules: [\"repairflow\"] when only RepairFlow is checked", async () => {
    mockPost.mockResolvedValue(SUCCESS_RESULT);
    renderPage();
    const user = userEvent.setup();
    await fillRequiredFields(user);
    await user.click(screen.getByLabelText("RepairFlow"));
    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(mockPost).toHaveBeenCalledWith("/platform-admin/companies", {
      company_name: "Нов Сервиз ЕООД",
      owner_name: "Иван Иванов",
      owner_email: "owner@dev-seed.bg",
      owner_password: "дълга-парола-1234",
      business_profile: "generic_repair",
      business_type_label: "Сервиз за велосипеди и тротинетки",
      modules: ["repairflow"],
    });
  });

  it("sends modules: [\"professional-services\"] when only PropertyFlow is checked", async () => {
    mockPost.mockResolvedValue({ ...SUCCESS_RESULT, activated_modules: ["professional-services"] });
    renderPage();
    const user = userEvent.setup();
    await fillRequiredFields(user);
    await user.click(screen.getByLabelText("PropertyFlow"));
    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(mockPost.mock.calls[0][1]).toMatchObject({ modules: ["professional-services"] });
  });

  it("is a radio group, not checkboxes — selecting the other option replaces, not adds", async () => {
    mockPost.mockResolvedValue({ ...SUCCESS_RESULT, activated_modules: ["professional-services"] });
    renderPage();
    const user = userEvent.setup();
    await fillRequiredFields(user);
    await user.click(screen.getByLabelText("RepairFlow"));
    await user.click(screen.getByLabelText("PropertyFlow"));

    expect(screen.getByLabelText("RepairFlow")).not.toBeChecked();
    expect(screen.getByLabelText("PropertyFlow")).toBeChecked();

    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(mockPost.mock.calls[0][1]).toMatchObject({ modules: ["professional-services"] });
  });

  it("targets the vendor-prefixed endpoint (proving the vendor CSRF branch applies)", async () => {
    mockPost.mockResolvedValue(SUCCESS_RESULT);
    renderPage();
    const user = userEvent.setup();
    await fillRequiredFields(user);
    await user.click(screen.getByLabelText("RepairFlow"));
    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    expect(mockPost.mock.calls[0][0]).toBe("/platform-admin/companies");
  });

  it("prevents a duplicate submission from a rapid double-click", async () => {
    let resolvePost: (v: typeof SUCCESS_RESULT) => void = () => {};
    mockPost.mockReturnValue(new Promise((resolve) => { resolvePost = resolve; }));
    renderPage();
    const user = userEvent.setup();
    await fillRequiredFields(user);
    await user.click(screen.getByLabelText("RepairFlow"));

    const button = screen.getByRole("button", { name: "Създай компания" });
    await user.click(button);
    await user.click(button);

    resolvePost(SUCCESS_RESULT);
    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
  });

  it("invalidates [\"vendor\",\"companies\"] on success and leaves tenant keys untouched", async () => {
    mockPost.mockResolvedValue(SUCCESS_RESULT);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["vendor", "companies"], [{ id: "old" }]);
    queryClient.setQueryData(["me"], { user_id: "u1" });
    renderPage(queryClient);
    const user = userEvent.setup();
    await fillRequiredFields(user);
    await user.click(screen.getByLabelText("RepairFlow"));
    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    await waitFor(() =>
      expect(queryClient.getQueryState(["vendor", "companies"])?.isInvalidated).toBe(true));
    expect(queryClient.getQueryData(["me"])).toEqual({ user_id: "u1" });
  });

  it("navigates to the new company's detail route on success", async () => {
    mockPost.mockResolvedValue(SUCCESS_RESULT);
    renderPage();
    const user = userEvent.setup();
    await fillRequiredFields(user);
    await user.click(screen.getByLabelText("RepairFlow"));
    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    expect(await screen.findByText("COMPANY_DETAIL_PAGE:c1")).toBeInTheDocument();
  });

  it("shows a useful message and clears the password on a 409 conflict, keeping other fields", async () => {
    mockPost.mockRejectedValue(
      new ApiError(409, "provisioning_failed", "errors.provisioning.owner_email_taken"),
    );
    renderPage();
    const user = userEvent.setup();
    await fillRequiredFields(user);
    await user.click(screen.getByLabelText("RepairFlow"));
    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    expect(await screen.findByText("Имейлът на собственика вече се използва.")).toBeInTheDocument();
    expect(screen.getByLabelText("Име на компанията")).toHaveValue("Нов Сервиз ЕООД");
    expect(screen.getByLabelText("Имейл")).toHaveValue("owner@dev-seed.bg");
    expect(screen.getByLabelText("Парола")).toHaveValue("");
  });

  it("maps a 422 field error onto the corresponding input", async () => {
    mockPost.mockRejectedValue(
      new ApiError(422, "validation_error", "errors.validation", {}, [
        { loc: ["body", "owner_email"], type: "value_error" },
      ]),
    );
    renderPage();
    const user = userEvent.setup();
    await fillRequiredFields(user);
    await user.click(screen.getByLabelText("RepairFlow"));
    await user.click(screen.getByRole("button", { name: "Създай компания" }));

    await waitFor(() => {
      const emailInput = screen.getByLabelText("Имейл");
      expect(emailInput).toHaveAttribute("class", expect.stringContaining("border-red-600"));
    });
  });

  it("shows a recoverable general error and re-enables submission on a 500", async () => {
    mockPost.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    renderPage();
    const user = userEvent.setup();
    await fillRequiredFields(user);
    await user.click(screen.getByLabelText("RepairFlow"));
    const button = screen.getByRole("button", { name: "Създай компания" });
    await user.click(button);

    expect(await screen.findByText("Възникна неочаквана грешка. Опитайте отново.")).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });
});
