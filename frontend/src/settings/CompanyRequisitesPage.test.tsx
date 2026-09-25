import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/Toast";
import { ApiError, api } from "../lib/api";
import { CompanyRequisitesPage } from "./CompanyRequisitesPage";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

const mockUseAuth = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

beforeEach(() => {
  vi.mocked(api.get).mockReset();
  vi.mocked(api.patch).mockReset();
});

function renderPage(isOwner = true) {
  mockUseAuth.mockReturnValue({ me: { is_owner: isOwner } });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter>
          <CompanyRequisitesPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CompanyRequisitesPage", () => {
  it("denies access to a non-owner without calling the API", () => {
    renderPage(false);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Достъпът е само за собственика на компанията.",
    );
    expect(api.get).not.toHaveBeenCalled();
  });

  it("still shows the settings sub-nav for a non-owner", () => {
    renderPage(false);

    expect(screen.getByRole("link", { name: "Служители" })).toHaveAttribute(
      "href", "/settings/employees",
    );
    expect(screen.getByRole("link", { name: "Фирма" })).toHaveAttribute(
      "href", "/settings/company",
    );
  });

  it("loads and pre-fills the current requisites for an owner", async () => {
    vi.mocked(api.get).mockResolvedValue({
      address: "гр. София, ул. Тестова 1", phone: "029876543", eik: "130489869",
      vat_registered: true,
    });
    renderPage();

    expect(await screen.findByDisplayValue("гр. София, ул. Тестова 1")).toBeInTheDocument();
    expect(screen.getByDisplayValue("029876543")).toBeInTheDocument();
    expect(screen.getByDisplayValue("130489869")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Регистрация по ЗДДС" })).toBeChecked();
  });

  it("submits the edited fields via PATCH and shows a success toast", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({
      address: null, phone: null, eik: null, vat_registered: false,
    });
    vi.mocked(api.patch).mockResolvedValue({
      address: "гр. Пловдив", phone: "032111222", eik: null, vat_registered: false,
    });
    renderPage();

    await screen.findByLabelText("Адрес");
    await user.type(screen.getByLabelText("Адрес"), "гр. Пловдив");
    await user.type(screen.getByLabelText("Телефон"), "032111222");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/company/requisites", {
      address: "гр. Пловдив", phone: "032111222", eik: "", vat_registered: false,
    });
    expect(await screen.findByText("Данните за фирмата са запазени.")).toBeInTheDocument();
  });

  it("saves an edited ЕИК via PATCH", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({
      address: null, phone: null, eik: null, vat_registered: false,
    });
    vi.mocked(api.patch).mockResolvedValue({
      address: null, phone: null, eik: "130489869", vat_registered: false,
    });
    renderPage();

    await screen.findByLabelText("ЕИК / БУЛСТАТ");
    await user.type(screen.getByLabelText("ЕИК / БУЛСТАТ"), "130489869");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/company/requisites", {
      address: "", phone: "", eik: "130489869", vat_registered: false,
    });
    expect(await screen.findByText("Данните за фирмата са запазени.")).toBeInTheDocument();
  });

  it("renders a save error inline instead of silently failing", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({
      address: null, phone: null, eik: null, vat_registered: false,
    });
    vi.mocked(api.patch).mockRejectedValue(
      new ApiError(402, "subscription_not_active", "errors.subscription.mutations_blocked"),
    );
    renderPage();

    await screen.findByLabelText("Адрес");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(await screen.findByText(
      "Промени не са позволени — абонаментът на компанията не е активен.",
    )).toBeInTheDocument();
  });
});

describe("CompanyRequisitesPage — Wave 4 Issue 38 (warranty defaults)", () => {
  function mockGetByPath(byPath: Record<string, unknown>) {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path in byPath) return Promise.resolve(byPath[path]) as never;
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
  }

  const REQUISITES = { address: null, phone: null, eik: null, vat_registered: false };

  it("shows an empty input for a null default and the literal 0 for an explicit zero", async () => {
    mockGetByPath({
      "/company/requisites": REQUISITES,
      "/company/warranty-defaults": { labor_days: 0, parts_days: null },
    });
    renderPage();

    expect(await screen.findByLabelText("Гаранция за труд (дни)")).toHaveValue(0);
    expect(screen.getByLabelText("Гаранция за части (дни)")).toHaveValue(null);
  });

  it("prefills positive-day defaults", async () => {
    mockGetByPath({
      "/company/requisites": REQUISITES,
      "/company/warranty-defaults": { labor_days: 90, parts_days: 30 },
    });
    renderPage();

    expect(await screen.findByLabelText("Гаранция за труд (дни)")).toHaveValue(90);
    expect(screen.getByLabelText("Гаранция за части (дни)")).toHaveValue(30);
  });

  it("saves warranty defaults via its own PATCH, independent of the requisites form", async () => {
    const user = userEvent.setup();
    mockGetByPath({
      "/company/requisites": REQUISITES,
      "/company/warranty-defaults": { labor_days: null, parts_days: null },
    });
    vi.mocked(api.patch).mockResolvedValue({ labor_days: 90, parts_days: 0 });
    renderPage();

    await user.type(await screen.findByLabelText("Гаранция за труд (дни)"), "90");
    await user.type(screen.getByLabelText("Гаранция за части (дни)"), "0");
    await user.click(screen.getByRole("button", { name: "Запази гаранцията" }));

    expect(api.patch).toHaveBeenCalledWith("/company/warranty-defaults", {
      labor_days: 90, parts_days: 0,
      standard_term: null, conditions: null, text: null, additional_conditions: null,
    });
    expect(await screen.findByText("Гаранцията по подразбиране е запазена.")).toBeInTheDocument();
    // The requisites PATCH must never have been touched by this save.
    expect(api.patch).not.toHaveBeenCalledWith("/company/requisites", expect.anything());
  });

  it("sends null for a field left empty", async () => {
    const user = userEvent.setup();
    mockGetByPath({
      "/company/requisites": REQUISITES,
      "/company/warranty-defaults": { labor_days: 90, parts_days: 30 },
    });
    vi.mocked(api.patch).mockResolvedValue({ labor_days: null, parts_days: 30 });
    renderPage();

    const laborInput = await screen.findByLabelText("Гаранция за труд (дни)");
    await user.clear(laborInput);
    await user.click(screen.getByRole("button", { name: "Запази гаранцията" }));

    expect(api.patch).toHaveBeenCalledWith("/company/warranty-defaults", {
      labor_days: null, parts_days: 30,
      standard_term: null, conditions: null, text: null, additional_conditions: null,
    });
  });
});

describe("CompanyRequisitesPage — issue 04 (free-text warranty terms)", () => {
  function mockGetByPath(byPath: Record<string, unknown>) {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path in byPath) return Promise.resolve(byPath[path]) as never;
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
  }

  const REQUISITES = { address: null, phone: null, eik: null, vat_registered: false };
  const BLANK_TERMS = {
    standard_term: null, conditions: null, text: null, additional_conditions: null,
  };

  it("prefills the four text fields from the backend", async () => {
    mockGetByPath({
      "/company/requisites": REQUISITES,
      "/company/warranty-defaults": {
        labor_days: null, parts_days: null,
        standard_term: "12 месеца", conditions: "Условие А",
        text: "Пълен текст", additional_conditions: "Допълнително Б",
      },
    });
    renderPage();

    expect(await screen.findByLabelText("Стандартен гаранционен срок")).toHaveValue("12 месеца");
    expect(screen.getByLabelText("Гаранционни условия")).toHaveValue("Условие А");
    expect(screen.getByLabelText("Текст на гаранцията")).toHaveValue("Пълен текст");
    expect(screen.getByLabelText("Допълнителни условия")).toHaveValue("Допълнително Б");
  });

  it("saves the four text fields, trimmed, alongside the numeric defaults", async () => {
    const user = userEvent.setup();
    mockGetByPath({
      "/company/requisites": REQUISITES,
      "/company/warranty-defaults": { labor_days: null, parts_days: null, ...BLANK_TERMS },
    });
    vi.mocked(api.patch).mockResolvedValue({ labor_days: null, parts_days: null, ...BLANK_TERMS });
    renderPage();

    await user.type(await screen.findByLabelText("Стандартен гаранционен срок"), "  12 месеца  ");
    await user.type(screen.getByLabelText("Гаранционни условия"), "Условие");
    await user.click(screen.getByRole("button", { name: "Запази гаранцията" }));

    expect(api.patch).toHaveBeenCalledWith("/company/warranty-defaults", {
      labor_days: null, parts_days: null,
      standard_term: "12 месеца", conditions: "Условие", text: null, additional_conditions: null,
    });
  });

  it("sends null for a text field left blank", async () => {
    const user = userEvent.setup();
    mockGetByPath({
      "/company/requisites": REQUISITES,
      "/company/warranty-defaults": {
        labor_days: null, parts_days: null, standard_term: "12 месеца",
        conditions: null, text: null, additional_conditions: null,
      },
    });
    vi.mocked(api.patch).mockResolvedValue({ labor_days: null, parts_days: null, ...BLANK_TERMS });
    renderPage();

    const input = await screen.findByLabelText("Стандартен гаранционен срок");
    await user.clear(input);
    await user.click(screen.getByRole("button", { name: "Запази гаранцията" }));

    expect(api.patch).toHaveBeenCalledWith("/company/warranty-defaults", {
      labor_days: null, parts_days: null, ...BLANK_TERMS,
    });
  });
});
