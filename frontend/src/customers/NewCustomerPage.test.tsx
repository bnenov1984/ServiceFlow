import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../lib/api";
import { NewCustomerPage } from "./NewCustomerPage";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { ...actual.api, get: vi.fn(), post: vi.fn() } };
});

beforeEach(() => {
  vi.mocked(api.get).mockReset();
  vi.mocked(api.post).mockReset();
  // No duplicate by default — the on-blur phone/ЕИК pre-check (order-
  // workflow-revamp WP-B) shouldn't interfere with tests that don't care
  // about it.
  vi.mocked(api.get).mockResolvedValue({ duplicate: null });
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/customers/new"]}>
        <Routes>
          <Route path="/customers/new" element={<NewCustomerPage />} />
          <Route path="/customers/:id" element={<div>CUSTOMER_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("NewCustomerPage — Wave 5 Issue 14 (standalone Add Customer)", () => {
  it("creates an individual customer and navigates to their profile, without creating an order", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "c1", name: "Иван Петров", phone: "0888123456",
    });
    renderPage();

    await user.type(screen.getByPlaceholderText("Име"), "Иван Петров");
    await user.type(screen.getByPlaceholderText("Телефон"), "0888123456");
    await user.click(screen.getByRole("button", { name: "Създай клиент" }));

    expect(api.post).toHaveBeenCalledWith("/customers", expect.objectContaining({
      name: "Иван Петров", phone: "0888123456", is_company: false,
    }));
    // Exactly one request — no order was ever created alongside it.
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("CUSTOMER_PAGE")).toBeInTheDocument();
  });

  it("creates a company customer with the Wave 5 fields", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "c2", name: "Пример ЕООД", phone: "029001122",
    });
    renderPage();

    await user.type(screen.getByPlaceholderText("Име"), "Пример ЕООД");
    await user.type(screen.getByPlaceholderText("Телефон"), "029001122");
    await user.click(screen.getByRole("button", { name: "Фирма" }));
    await user.type(screen.getByLabelText("Адрес"), "гр. София");
    await user.type(screen.getByLabelText("ЕИК / БУЛСТАТ"), "130489869");
    await user.click(screen.getByRole("button", { name: "Създай клиент" }));

    expect(api.post).toHaveBeenCalledWith("/customers", expect.objectContaining({
      is_company: true,
      company_requisites: expect.objectContaining({
        country: "BG", address: "гр. София", eik: "130489869",
      }),
    }));
    expect(await screen.findByText("CUSTOMER_PAGE")).toBeInTheDocument();
  });

  it("sends an individual's own main address (order-workflow-revamp WP-B, Q20)", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "c3", name: "Иван Петров", phone: "0888123456",
    });
    renderPage();

    await user.type(screen.getByPlaceholderText("Име"), "Иван Петров");
    await user.type(screen.getByPlaceholderText("Телефон"), "0888123456");
    await user.type(screen.getByPlaceholderText("Адрес"), "ул. Тестова 5");
    await user.click(screen.getByRole("button", { name: "Създай клиент" }));

    expect(api.post).toHaveBeenCalledWith("/customers", expect.objectContaining({
      address: "ул. Тестова 5",
    }));
  });

  it("an on-blur duplicate phone offers a link to the existing customer, no resolve callback here", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({
      duplicate: { id: "existing-1", name: "Иван Петров" },
    });
    renderPage();

    await user.type(screen.getByPlaceholderText("Име"), "Иван Петров (дубликат)");
    await user.type(screen.getByPlaceholderText("Телефон"), "0888123456");
    await user.tab();

    const link = await screen.findByRole("link", { name: "Избери съществуващия клиент" });
    expect(link).toHaveAttribute("href", "/customers/existing-1");
    expect(screen.getByRole("button", { name: "Създай клиент" })).toBeDisabled();
  });

  it("an on-blur duplicate ЕИК offers a link to the existing company (order-workflow-revamp WP-B, Q8)", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({
      duplicate: { id: "existing-co", name: "Пример ЕООД" },
    });
    renderPage();

    await user.type(screen.getByPlaceholderText("Име"), "Пример ЕООД (дубликат)");
    await user.type(screen.getByPlaceholderText("Телефон"), "029001122");
    await user.click(screen.getByRole("button", { name: "Фирма" }));
    await user.type(screen.getByLabelText("ЕИК / БУЛСТАТ"), "130489869");
    await user.tab();

    const link = await screen.findByRole("link", { name: "Избери тази фирма" });
    expect(link).toHaveAttribute("href", "/customers/existing-co");
    expect(screen.getByRole("button", { name: "Създай клиент" })).toBeDisabled();
  });

  it("surfaces the backend's validation error the same way intake does (shared error handling)", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(400, "validation_error", "errors.validation"),
    );
    renderPage();

    await user.type(screen.getByPlaceholderText("Име"), "Пример ЕООД");
    await user.type(screen.getByPlaceholderText("Телефон"), "029001122");
    await user.click(screen.getByRole("button", { name: "Фирма" }));
    await user.type(screen.getByLabelText("ЕИК / БУЛСТАТ"), "12345");
    await user.click(screen.getByRole("button", { name: "Създай клиент" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText("CUSTOMER_PAGE")).not.toBeInTheDocument();
  });
});
