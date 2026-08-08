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
      address: "гр. София, ул. Тестова 1", phone: "029876543", vat_registered: true,
    });
    renderPage();

    expect(await screen.findByDisplayValue("гр. София, ул. Тестова 1")).toBeInTheDocument();
    expect(screen.getByDisplayValue("029876543")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Регистрация по ЗДДС" })).toBeChecked();
  });

  it("submits the edited fields via PATCH and shows a success toast", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({ address: null, phone: null, vat_registered: false });
    vi.mocked(api.patch).mockResolvedValue({
      address: "гр. Пловдив", phone: "032111222", vat_registered: false,
    });
    renderPage();

    await screen.findByLabelText("Адрес");
    await user.type(screen.getByLabelText("Адрес"), "гр. Пловдив");
    await user.type(screen.getByLabelText("Телефон"), "032111222");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/company/requisites", {
      address: "гр. Пловдив", phone: "032111222", vat_registered: false,
    });
    expect(await screen.findByText("Данните за фирмата са запазени.")).toBeInTheDocument();
  });

  it("renders a save error inline instead of silently failing", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({ address: null, phone: null, vat_registered: false });
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
