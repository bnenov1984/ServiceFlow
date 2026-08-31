import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../lib/api";
import { NewCustomerPage } from "./NewCustomerPage";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { ...actual.api, post: vi.fn() } };
});

beforeEach(() => {
  vi.mocked(api.post).mockReset();
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
      id: "c1", name: "Иван Петров", phone: "0888123456", duplicate_ids: [],
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
      id: "c2", name: "Пример ЕООД", phone: "029001122", duplicate_ids: [],
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
