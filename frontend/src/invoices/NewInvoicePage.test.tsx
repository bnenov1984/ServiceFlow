import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../lib/api";
import { NewInvoicePage } from "./NewInvoicePage";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { ...actual.api, get: vi.fn(), post: vi.fn() } };
});

beforeEach(() => {
  vi.mocked(api.get).mockReset();
  vi.mocked(api.post).mockReset();
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/invoices/new"]}>
        <Routes>
          <Route path="/invoices/new" element={<NewInvoicePage />} />
          <Route path="/invoices/:id" element={<div>INVOICE_DETAIL_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const customerHit = { id: "cust-1", name: "Иван Петров", phone: "0888123456", archived: false };

describe("NewInvoicePage — Wave 6 Issue 30 (manual invoice creation)", () => {
  it("creates a manual invoice for an existing customer found via search, without creating an order", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue([customerHit]);
    vi.mocked(api.post).mockResolvedValue({
      id: "inv-1", order_id: null, customer_id: "cust-1", status: "draft",
      number: null, currency: "EUR", row_version: 1,
    });
    renderPage();

    await user.type(screen.getByPlaceholderText("Търсене по клиент…"), "Иван");
    await user.click(await screen.findByText("Иван Петров"));
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(api.post).toHaveBeenCalledWith("/invoices", { customer_id: "cust-1" });
    // Exactly one request — no order was ever created alongside it.
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("INVOICE_DETAIL_PAGE")).toBeInTheDocument();
  });

  it("disables Продължи until a customer is selected", async () => {
    vi.mocked(api.get).mockResolvedValue([]);
    renderPage();

    expect(screen.getByRole("button", { name: "Продължи" })).toBeDisabled();
  });

  it("creates a new customer inline, then creates the invoice for them", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockImplementation((path: string) => {
      if (path === "/customers") {
        return Promise.resolve({
          id: "cust-2", name: "Нов Клиент", phone: "0888999888",
        }) as never;
      }
      return Promise.resolve({
        id: "inv-2", order_id: null, customer_id: "cust-2", status: "draft",
        number: null, currency: "EUR", row_version: 1,
      }) as never;
    });
    renderPage();

    await user.click(screen.getByRole("button", { name: "+ Нов клиент" }));
    await user.type(screen.getByPlaceholderText("Име"), "Нов Клиент");
    await user.type(screen.getByPlaceholderText("Телефон"), "0888999888");
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(api.post).toHaveBeenNthCalledWith(1, "/customers", expect.objectContaining({
      name: "Нов Клиент", phone: "0888999888",
    }));
    expect(api.post).toHaveBeenNthCalledWith(2, "/invoices", { customer_id: "cust-2" });
    expect(await screen.findByText("INVOICE_DETAIL_PAGE")).toBeInTheDocument();
  });

  it("surfaces a backend error from invoice creation without navigating away", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue([customerHit]);
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(404, "not_found", "errors.invoices.customer_not_found"),
    );
    renderPage();

    await user.type(screen.getByPlaceholderText("Търсене по клиент…"), "Иван");
    await user.click(await screen.findByText("Иван Петров"));
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Няма такъв клиент.");
    expect(screen.queryByText("INVOICE_DETAIL_PAGE")).not.toBeInTheDocument();
  });
});
