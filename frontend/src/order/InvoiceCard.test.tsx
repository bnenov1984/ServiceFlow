import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/Toast";
import { ApiError, api } from "../lib/api";
import { InvoiceCard } from "./InvoiceCard";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

const orderId = "order-1";

function renderCard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
  return render(<InvoiceCard orderId={orderId} />, { wrapper: Wrapper });
}

const draftListItem = {
  id: "inv-1", order_id: orderId, status: "draft", number: null,
  currency: "EUR", row_version: 1,
};

const draftDetail = {
  ...draftListItem,
  lines: [
    { id: "l1", description: "Дисплей", qty: 1, unit_price: 100, vat_rate: null, source: "part" },
    { id: "l2", description: "Смяна на дисплей", qty: 1, unit_price: 50, vat_rate: null, source: "labor" },
  ],
  draft_total: 150,
};

describe("InvoiceCard", () => {
  it("shows the empty state and create button when no draft exists", async () => {
    vi.mocked(api.get).mockResolvedValue([]);
    renderCard();

    expect(await screen.findByText("Няма чернова на фактура.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Създай чернова" })).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith(`/invoices?order_id=${orderId}&status=draft`);
  });

  it("creates a draft via POST and opens it", async () => {
    const user = userEvent.setup();
    let created = false;
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path.startsWith("/invoices?")) return Promise.resolve(created ? [draftListItem] : []) as never;
      return Promise.resolve(draftDetail) as never;
    });
    vi.mocked(api.post).mockImplementation(() => {
      created = true;
      return Promise.resolve(draftDetail) as never;
    });
    renderCard();

    await user.click(await screen.findByRole("button", { name: "Създай чернова" }));

    expect(api.post).toHaveBeenCalledWith(`/orders/${orderId}/invoices`);
    expect(await screen.findByText("Чернова")).toBeInTheDocument();
    expect(await screen.findByDisplayValue("Дисплей")).toBeInTheDocument();
  });

  it("shows prefilled part/labor lines with their source preserved when opened", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockImplementation((path: string) =>
      Promise.resolve(path.startsWith("/invoices?") ? [draftListItem] : draftDetail) as never,
    );
    renderCard();

    await user.click(await screen.findByRole("button", { name: "Отвори" }));

    expect(await screen.findByDisplayValue("Дисплей")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Смяна на дисплей")).toBeInTheDocument();
    expect(screen.getByText("Част")).toBeInTheDocument();
    expect(screen.getByText("Труд")).toBeInTheDocument();
    expect(screen.getByText("150.00 €")).toBeInTheDocument(); // backend draft_total
  });

  it("edits a line, adds a manual line, removes a line, then saves the full replacement", async () => {
    const user = userEvent.setup();
    const savedDetail = {
      ...draftDetail,
      lines: [
        { id: "l1", description: "Дисплей (нов)", qty: 1, unit_price: 100, vat_rate: null, source: "part" },
        { id: "l3", description: "Транспорт", qty: 1, unit_price: 20, vat_rate: null, source: "manual" },
      ],
      draft_total: 120,
    };
    let saved = false;
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path.startsWith("/invoices?")) return Promise.resolve([draftListItem]) as never;
      return Promise.resolve(saved ? savedDetail : draftDetail) as never;
    });
    vi.mocked(api.patch).mockImplementation(() => {
      saved = true;
      return Promise.resolve(savedDetail) as never;
    });
    renderCard();

    await user.click(await screen.findByRole("button", { name: "Отвори" }));
    await screen.findByDisplayValue("Дисплей");

    // edit an existing (prefilled) line's description
    const descriptionInputs = screen.getAllByPlaceholderText("Описание…");
    await user.clear(descriptionInputs[0]);
    await user.type(descriptionInputs[0], "Дисплей (нов)");

    // remove the labor line
    const removeButtons = screen.getAllByRole("button", { name: "Премахни ред" });
    await user.click(removeButtons[1]);

    // add a manual line — the last remaining "Описание…" field is the add-form
    const descriptionFields = screen.getAllByPlaceholderText("Описание…");
    const addDescription = descriptionFields[descriptionFields.length - 1];
    await user.type(addDescription, "Транспорт");
    const priceInputs = screen.getAllByLabelText("Цена (€)");
    await user.type(priceInputs[priceInputs.length - 1], "20");
    await user.click(screen.getByRole("button", { name: "Добави" }));

    await user.click(screen.getByRole("button", { name: "Запази" }));

    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1));
    const [path, body] = vi.mocked(api.patch).mock.calls[0] as [string, { lines: unknown[] }];
    expect(path).toBe("/invoices/inv-1");
    expect(body.lines).toEqual([
      { description: "Дисплей (нов)", qty: 1, unit_price: 100, source: "part" },
      { description: "Транспорт", qty: 1, unit_price: 20, source: "manual" },
    ]);

    expect(await screen.findByText("120.00 €")).toBeInTheDocument();
  });

  it("keeps saved state on close then reopen (no stale unsaved edits)", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockImplementation((path: string) =>
      Promise.resolve(path.startsWith("/invoices?") ? [draftListItem] : draftDetail) as never,
    );
    renderCard();

    await user.click(await screen.findByRole("button", { name: "Отвори" }));
    await screen.findByDisplayValue("Дисплей");

    await user.click(screen.getByRole("button", { name: "Затвори чернова" }));
    expect(screen.queryByDisplayValue("Дисплей")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Отвори" }));
    expect(await screen.findByDisplayValue("Дисплей")).toBeInTheDocument();
    expect(screen.getByText("150.00 €")).toBeInTheDocument();
  });

  it("renders a backend error by its translated message_key, not raw text", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue([]);
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, "order_error", "errors.orders.archived"),
    );
    renderCard();

    await user.click(await screen.findByRole("button", { name: "Създай чернова" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Поръчката е архивирана.");
  });

  it("keeps the issue action disabled with no fake number or PDF", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockImplementation((path: string) =>
      Promise.resolve(path.startsWith("/invoices?") ? [draftListItem] : draftDetail) as never,
    );
    renderCard();

    await user.click(await screen.findByRole("button", { name: "Отвори" }));

    const issueButton = await screen.findByRole("button", { name: "Издай фактура" });
    expect(issueButton).toBeDisabled();
    expect(screen.queryByText(/№\s*\d/)).not.toBeInTheDocument();
    expect(document.querySelector('a[href$=".pdf"]')).not.toBeInTheDocument();
  });
});
