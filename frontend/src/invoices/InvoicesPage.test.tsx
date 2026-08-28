import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { api } from "../lib/api";
import { InvoicesPage } from "./InvoicesPage";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { ...actual.api, get: vi.fn() } };
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/invoices"]}>
        <Routes>
          <Route path="/invoices" element={children} />
          <Route path="/invoices/:id" element={<div>INVOICE_DETAIL_PAGE</div>} />
          <Route path="/orders/:id" element={<div>ORDER_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
  return render(<InvoicesPage />, { wrapper: Wrapper });
}

const draftRow = {
  id: "inv-draft", order_id: "order-1", order_number: "2026-00002", status: "draft",
  number: null, currency: "EUR", customer_name: "Драфт Клиент", issued_at: null,
  tax_event_date: null, total: 30, row_version: 1,
};

const issuedRow = {
  id: "inv-issued", order_id: "order-2", order_number: "2026-00001", status: "issued",
  number: 1, currency: "EUR", customer_name: "Издаден Клиент",
  issued_at: "2026-03-15T10:30:00Z", tax_event_date: "2026-03-15", total: 150, row_version: 2,
};

afterEach(() => {
  vi.mocked(api.get).mockReset();
});

describe("InvoicesPage: loading / empty / error", () => {
  it("shows a loading state before data arrives", () => {
    vi.mocked(api.get).mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(document.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("shows the empty state with no global 'Нова фактура' button", async () => {
    vi.mocked(api.get).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/Все още няма фактури/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Нова фактура/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Нова фактура/ })).not.toBeInTheDocument();
  });

  it("shows an error state on API failure with a working retry", async () => {
    vi.mocked(api.get).mockRejectedValue(new ApiError(500, "internal_error", "errors.internal"));
    renderPage();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

describe("InvoicesPage: rows", () => {
  it("renders a Draft row: no number, Чернова, customer, order number, total, Отвори, no PDF", async () => {
    vi.mocked(api.get).mockResolvedValue([draftRow]);
    renderPage();
    const row = (await screen.findByText("Драфт Клиент")).closest("tr");
    expect(row).not.toBeNull();
    const within_ = within(row as HTMLElement);
    // Draft row: both the Number column ("no legal number yet") and the Date
    // column ("issued_at is only ever set once issued") render "—".
    expect(within_.getAllByText("—")).toHaveLength(2);
    expect(within_.getByText("Чернова")).toBeInTheDocument();
    expect(within_.getByText("2026-00002")).toBeInTheDocument();
    expect(within_.getByText("30.00 €")).toBeInTheDocument();
    expect(within_.getByRole("link", { name: "Отвори" })).toHaveAttribute("href", "/invoices/inv-draft");
    expect(within_.queryByRole("button", { name: "PDF" })).not.toBeInTheDocument();
  });

  it("renders an Issued row: 10-digit number, Издадена, customer, issued date, total, Отвори, PDF", async () => {
    vi.mocked(api.get).mockResolvedValue([issuedRow]);
    renderPage();
    const row = (await screen.findByText("Издаден Клиент")).closest("tr");
    expect(row).not.toBeNull();
    const within_ = within(row as HTMLElement);
    expect(within_.getByText("0000000001")).toBeInTheDocument();
    expect(within_.getByText("Издадена")).toBeInTheDocument();
    expect(within_.getByText(new Date(issuedRow.issued_at).toLocaleString("bg-BG"))).toBeInTheDocument();
    expect(within_.getByText("150.00 €")).toBeInTheDocument();
    expect(within_.getByRole("link", { name: "Отвори" })).toHaveAttribute("href", "/invoices/inv-issued");
    expect(within_.getByRole("button", { name: "PDF" })).toBeInTheDocument();
  });

  it("'Отвори' on a Draft row navigates to the Invoice Detail page, not the order", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue([draftRow]);
    renderPage();
    await user.click(await screen.findByRole("link", { name: "Отвори" }));
    expect(await screen.findByText("INVOICE_DETAIL_PAGE")).toBeInTheDocument();
    expect(screen.queryByText("ORDER_PAGE")).not.toBeInTheDocument();
  });

  it("'Отвори' on an Issued row navigates to the Invoice Detail page, not the order", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue([issuedRow]);
    renderPage();
    await user.click(await screen.findByRole("link", { name: "Отвори" }));
    expect(await screen.findByText("INVOICE_DETAIL_PAGE")).toBeInTheDocument();
    expect(screen.queryByText("ORDER_PAGE")).not.toBeInTheDocument();
  });

  it("the Order-number link still navigates to the Service Order, distinct from 'Отвори'", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue([issuedRow]);
    renderPage();
    await user.click(await screen.findByRole("link", { name: "2026-00001" }));
    expect(await screen.findByText("ORDER_PAGE")).toBeInTheDocument();
    expect(screen.queryByText("INVOICE_DETAIL_PAGE")).not.toBeInTheDocument();
  });

  it("PDF action targets the existing issued-invoice PDF endpoint", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue([issuedRow]);
    renderPage();
    await user.click(await screen.findByRole("button", { name: "PDF" }));
    expect(openSpy).toHaveBeenCalledWith("/api/v1/invoices/inv-issued/invoice.pdf", "_blank");
    openSpy.mockRestore();
  });
});

describe("InvoicesPage: status filter", () => {
  it("Всички omits the status query param", async () => {
    vi.mocked(api.get).mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    const url = vi.mocked(api.get).mock.calls[0][0] as string;
    expect(url).not.toContain("status=");
  });

  it("Чернови sends status=draft", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue([]);
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Чернови" }));
    await waitFor(() => {
      const lastUrl = vi.mocked(api.get).mock.calls.at(-1)?.[0] as string;
      expect(lastUrl).toContain("status=draft");
    });
  });

  it("Издадени sends status=issued", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue([]);
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Издадени" }));
    await waitFor(() => {
      const lastUrl = vi.mocked(api.get).mock.calls.at(-1)?.[0] as string;
      expect(lastUrl).toContain("status=issued");
    });
  });

  it("switching the filter resets pagination — old rows are gone once the new page resolves", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValueOnce([draftRow]);
    renderPage();
    expect(await screen.findByText("Драфт Клиент")).toBeInTheDocument();

    vi.mocked(api.get).mockResolvedValueOnce([issuedRow]);
    await user.click(screen.getByRole("button", { name: "Издадени" }));

    await waitFor(() => expect(screen.queryByText("Драфт Клиент")).not.toBeInTheDocument());
    expect(await screen.findByText("Издаден Клиент")).toBeInTheDocument();
  });
});

describe("InvoicesPage: customer filter (Issue 39)", () => {
  const customerHit = { id: "cust-1", name: "Иван Петров", phone: "0888123456", archived: false };

  function mockInvoicesAndCustomerSearch() {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path.startsWith("/customers")) return Promise.resolve([customerHit]) as never;
      return Promise.resolve([]) as never;
    });
  }

  it("selecting a customer from search sends customer_id, composed with the status filter", async () => {
    const user = userEvent.setup();
    mockInvoicesAndCustomerSearch();
    renderPage();

    await user.type(screen.getByPlaceholderText("Търсене по клиент…"), "Иван");
    await user.click(await screen.findByText("Иван Петров"));

    await waitFor(() => {
      const lastUrl = vi.mocked(api.get).mock.calls.at(-1)?.[0] as string;
      expect(lastUrl).toContain("/invoices");
      expect(lastUrl).toContain(`customer_id=${customerHit.id}`);
    });

    await user.click(screen.getByRole("button", { name: "Издадени" }));
    await waitFor(() => {
      const lastUrl = vi.mocked(api.get).mock.calls.at(-1)?.[0] as string;
      expect(lastUrl).toContain(`customer_id=${customerHit.id}`);
      expect(lastUrl).toContain("status=issued");
    });
  });

  it("clearing the selected customer removes customer_id from the next request", async () => {
    const user = userEvent.setup();
    mockInvoicesAndCustomerSearch();
    renderPage();

    await user.type(screen.getByPlaceholderText("Търсене по клиент…"), "Иван");
    await user.click(await screen.findByText("Иван Петров"));
    await screen.findByText(customerHit.name);

    await user.click(screen.getByRole("button", { name: "Изчисти" }));

    await waitFor(() => {
      const lastUrl = vi.mocked(api.get).mock.calls.at(-1)?.[0] as string;
      expect(lastUrl).not.toContain("customer_id");
    });
    expect(screen.getByPlaceholderText("Търсене по клиент…")).toBeInTheDocument();
  });

  it("Load More preserves the active customer filter on subsequent pages", async () => {
    const user = userEvent.setup();
    const fullInvoicePage = Array.from({ length: 50 }, (_, i) => ({
      ...draftRow, id: `p1-${i}`, order_id: `order-p1-${i}`,
    }));
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path.startsWith("/customers")) return Promise.resolve([customerHit]) as never;
      return Promise.resolve(fullInvoicePage) as never;
    });
    renderPage();

    await user.type(screen.getByPlaceholderText("Търсене по клиент…"), "Иван");
    await user.click(await screen.findByText("Иван Петров"));
    const loadMore = await screen.findByRole("button", { name: "Зареди още" });

    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path.startsWith("/customers")) return Promise.resolve([customerHit]) as never;
      return Promise.resolve([]) as never;
    });
    await user.click(loadMore);

    await waitFor(() => {
      const lastUrl = vi.mocked(api.get).mock.calls.at(-1)?.[0] as string;
      expect(lastUrl).toContain("/invoices");
      expect(lastUrl).toContain(`customer_id=${customerHit.id}`);
    });
  });
});

describe("InvoicesPage: Load More pagination", () => {
  function fullPage(prefix: string, n: number) {
    return Array.from({ length: n }, (_, i) => ({
      ...draftRow, id: `${prefix}-${i}`, order_id: `order-${prefix}-${i}`,
      order_number: `2026-${String(i).padStart(5, "0")}`, customer_name: `Клиент ${prefix}-${i}`,
    }));
  }

  it("shows Зареди още only when a full page is returned, and appends the next page", async () => {
    const user = userEvent.setup();
    const page1 = fullPage("p1", 50);
    const page2 = fullPage("p2", 10);
    vi.mocked(api.get).mockResolvedValueOnce(page1).mockResolvedValueOnce(page2);
    renderPage();

    const loadMore = await screen.findByRole("button", { name: "Зареди още" });
    await user.click(loadMore);

    await waitFor(() => expect(screen.getByText("Клиент p2-0")).toBeInTheDocument());
    expect(screen.getByText("Клиент p1-0")).toBeInTheDocument();
    // page2 has fewer than 50 rows -> no more Load More afterward.
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Зареди още" })).not.toBeInTheDocument(),
    );
  });

  it("does not show Зареди още when the first page is short", async () => {
    vi.mocked(api.get).mockResolvedValue([draftRow]);
    renderPage();
    await screen.findByText("Драфт Клиент");
    expect(screen.queryByRole("button", { name: "Зареди още" })).not.toBeInTheDocument();
  });

  it("prevents a duplicate Load More submission while one is pending", async () => {
    const user = userEvent.setup();
    const page1 = fullPage("p1", 50);
    let resolveSecond: (value: typeof page1) => void = () => {};
    const second = new Promise<typeof page1>((resolve) => { resolveSecond = resolve; });
    vi.mocked(api.get).mockResolvedValueOnce(page1).mockImplementationOnce(() => second);
    renderPage();

    const loadMore = await screen.findByRole("button", { name: "Зареди още" });
    await user.click(loadMore);
    await user.click(loadMore); // second click while the first is still pending
    resolveSecond(fullPage("p2", 5));

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2)); // first page + exactly one more page
  });
});
