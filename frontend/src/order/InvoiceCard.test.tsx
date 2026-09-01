import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/Toast";
import { queryKeys } from "../lib/queryKeys";
import { ApiError, api } from "../lib/api";
import { InvoiceCard } from "./InvoiceCard";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

const mockUseAuth = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

const orderId = "order-1";

function renderCard(deliveredAt: string | null = null, isOwner = true, customerId?: string) {
  mockUseAuth.mockReturnValue({ me: { is_owner: isOwner } });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter>{children}</MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
  const view = render(
    <InvoiceCard orderId={orderId} deliveredAt={deliveredAt} customerId={customerId} />,
    { wrapper: Wrapper },
  );
  return { ...view, client };
}

const draftListItem = {
  id: "inv-1", order_id: orderId, status: "draft", number: null,
  currency: "EUR", row_version: 1,
};

const baseDraftDetail = {
  ...draftListItem,
  lines: [
    { id: "l1", description: "Дисплей", qty: 1, unit_price: 100, vat_rate: null, source: "part" },
    { id: "l2", description: "Смяна на дисплей", qty: 1, unit_price: 50, vat_rate: null, source: "labor" },
  ],
  draft_total: 150,
  tax_event_date: null, issued_at: null, seller: null, buyer: null,
  vat_mode: null, net: null, vat: null, gross: null,
};

const draftDetail = baseDraftDetail;

const issuedListItem = { ...draftListItem, status: "issued", number: 1, row_version: 2 };

const issuedDetail = {
  ...issuedListItem,
  lines: baseDraftDetail.lines,
  draft_total: 150,
  tax_event_date: "2026-03-15",
  issued_at: "2026-03-15T10:30:00Z",
  seller: {
    name: "Сервиз А", address: "гр. София, ул. Примерна 1",
    eik: "130489869", vat_registered: false,
  },
  buyer: { name: "Иван Петров" },
  vat_mode: "not_registered",
  net: 150, vat: 0, gross: 150,
};

const nonVatCompanyIssuedDetail = {
  ...issuedDetail,
  buyer: { name: "Пример ЕООД", address: "гр. Пловдив", eik: "130489869", vat_registered: false },
};

const vatCompanyIssuedDetail = {
  ...issuedDetail,
  buyer: {
    name: "ДДС ЕООД", address: "гр. Варна", eik: "130489869",
    vat_registered: true, vat_number: "BG130489869",
  },
};

const vatRegisteredSellerIssuedDetail = {
  ...issuedDetail,
  seller: {
    name: "Сервиз А", address: "гр. София, ул. Примерна 1",
    eik: "130489869", vat_registered: true, vat_number: "BG130489869",
  },
  vat_mode: "registered",
  net: 150, vat: 30, gross: 180,
};

function mockDraftFlow(): void {
  vi.mocked(api.get).mockImplementation((path: string) =>
    Promise.resolve(path.startsWith("/invoices?") ? [draftListItem] : draftDetail) as never,
  );
}

/** Models the real backend across the whole flow, not just the POST: once
 * Issue succeeds, a GET (e.g. the read-view's own useQuery re-mount/refetch)
 * must see the real issued state too — otherwise a stale-draft GET mock
 * would overwrite the response-seeded cache the moment any component
 * refetches, a test-double gap that doesn't exist against a real backend. */
function mockIssueSuccess(overrides: Partial<typeof issuedDetail> = {}): void {
  const finalIssued = { ...issuedDetail, ...overrides };
  let issued = false;
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.startsWith("/invoices?")) {
      return Promise.resolve([issued ? { ...issuedListItem, number: finalIssued.number } : draftListItem]) as never;
    }
    return Promise.resolve(issued ? finalIssued : draftDetail) as never;
  });
  vi.mocked(api.post).mockImplementation((path: string) => {
    if (path.endsWith("/issue")) {
      issued = true;
      return Promise.resolve(finalIssued) as never;
    }
    return Promise.resolve(draftDetail) as never;
  });
}

async function openDraft(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.click(await screen.findByRole("button", { name: "Отвори" }));
  await screen.findByDisplayValue("Дисплей");
}

async function openIssueDialog(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await openDraft(user);
  await user.click(screen.getByRole("button", { name: "Издай фактура" }));
  await screen.findByRole("heading", { name: "Издаване на фактура" });
}

/** The dialog's own confirm button, scoped to avoid ambiguity with the
 * trigger button of the same name that stays in the DOM (unhidden by
 * jsdom's <dialog> handling) once the dialog is open. */
function dialogConfirmButton(): HTMLElement {
  return within(screen.getByRole("dialog")).getByRole("button", { name: "Издай фактура" });
}

beforeEach(() => {
  vi.mocked(api.get).mockReset();
  vi.mocked(api.post).mockReset();
  vi.mocked(api.patch).mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("InvoiceCard", () => {
  it("shows the empty state and create button when no draft exists", async () => {
    vi.mocked(api.get).mockResolvedValue([]);
    renderCard();

    expect(await screen.findByText("Няма чернова на фактура.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Създай чернова" })).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith(`/invoices?order_id=${orderId}`);
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
    mockDraftFlow();
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

    await openDraft(user);

    const descriptionInputs = screen.getAllByPlaceholderText("Описание…");
    await user.clear(descriptionInputs[0]);
    await user.type(descriptionInputs[0], "Дисплей (нов)");

    const removeButtons = screen.getAllByRole("button", { name: "Премахни ред" });
    await user.click(removeButtons[1]);

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
    mockDraftFlow();
    renderCard();

    await openDraft(user);

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

  // --- Draft: Issue action -------------------------------------------

  it("Owner sees a real, enabled Issue action on a non-empty draft", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    renderCard(null, true);

    await openDraft(user);
    const issueButton = screen.getByRole("button", { name: "Издай фактура" });
    expect(issueButton).toBeInTheDocument();
    expect(issueButton).not.toBeDisabled();
    expect(screen.queryByText(/№\s*\d/)).not.toBeInTheDocument();
  });

  it("Worker never sees a usable Issue action", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    renderCard(null, false);

    await openDraft(user);
    expect(screen.queryByRole("button", { name: "Издай фактура" })).not.toBeInTheDocument();
  });

  it("disables Issue with an explanation when the draft has no lines", async () => {
    const user = userEvent.setup();
    const emptyDetail = { ...draftDetail, lines: [], draft_total: 0 };
    vi.mocked(api.get).mockImplementation((path: string) =>
      Promise.resolve(path.startsWith("/invoices?") ? [draftListItem] : emptyDetail) as never,
    );
    renderCard();

    await user.click(await screen.findByRole("button", { name: "Отвори" }));
    const issueButton = await screen.findByRole("button", { name: "Издай фактура" });
    expect(issueButton).toBeDisabled();
    expect(issueButton).toHaveAttribute("title", "Добавете поне един ред, преди да издадете фактура.");
  });

  it("opens the confirmation dialog on click", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    renderCard();

    await openIssueDialog(user);
    expect(screen.getByText(
      "След издаването фактурата получава окончателен номер и повече не може да бъде редактирана.",
    )).toBeInTheDocument();
  });

  it("does not show any permanent company-buyer warning by default", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    renderCard();

    await openIssueDialog(user);
    expect(screen.queryByText(
      "Фактури към фирми клиенти все още не се поддържат в тази версия.",
    )).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an editable tax event date field", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    const dateInput = screen.getByLabelText("Дата на данъчно събитие") as HTMLInputElement;
    expect(dateInput).toBeInTheDocument();
    await user.clear(dateInput);
    await user.type(dateInput, "2026-02-20");
    expect(dateInput).toHaveValue("2026-02-20");
  });

  it("defaults the date to the order's delivery date when available", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    renderCard("2026-02-10T18:45:00Z");

    await openIssueDialog(user);
    expect(screen.getByLabelText("Дата на данъчно събитие")).toHaveValue("2026-02-10");
  });

  it("defaults the date to today when no delivery date is available", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    renderCard(null);

    await openIssueDialog(user);

    const now = new Date();
    const expected = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-`
      + String(now.getDate()).padStart(2, "0");
    expect(screen.getByLabelText("Дата на данъчно събитие")).toHaveValue(expected);
  });

  it("cancel closes the dialog without calling the API", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    renderCard();

    await openIssueDialog(user);
    await user.click(screen.getByRole("button", { name: "Отказ" }));

    expect(screen.queryByLabelText("Дата на данъчно събитие")).not.toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("confirm sends exactly { tax_event_date }", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      "/invoices/inv-1/issue", { tax_event_date: "2026-02-10" },
    ));
  });

  it("sends exactly { tax_event_date } even when the resolved buyer is a company", async () => {
    const user = userEvent.setup();
    mockIssueSuccess(nonVatCompanyIssuedDetail);
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      "/invoices/inv-1/issue", { tax_event_date: "2026-02-10" },
    ));
  });

  it("prevents a duplicate submit while a request is pending", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    let resolvePost: (value: typeof issuedDetail) => void = () => {};
    vi.mocked(api.post).mockImplementation(
      () => new Promise((resolve) => { resolvePost = resolve; }) as never,
    );
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    const confirmButton = dialogConfirmButton();
    await user.click(confirmButton);
    await user.click(confirmButton);
    await user.click(confirmButton);

    expect(api.post).toHaveBeenCalledTimes(1);
    resolvePost(issuedDetail);
  });

  // --- Success: issued read-only view ---------------------------------

  it("switches to a read-only issued view after a successful Issue", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    expect(await screen.findByText("Издадена")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Дисплей")).not.toBeInTheDocument();
  });

  it("displays the exact 10-digit issued number with leading zeros", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    expect(await screen.findByText("Фактура № 0000000001")).toBeInTheDocument();
  });

  it("keeps its own internal header (status badge + number + PDF) — embedded default is unchanged by the standalone Invoice Detail page", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    const { container } = renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await screen.findByText("Фактура № 0000000001");
    // The section title ("Фактура", InvoiceCard's own h3) plus
    // IssuedInvoiceView's own internal badge/number/PDF row are both
    // present — InvoiceCard never passes embedded={false}, so
    // IssuedInvoiceView keeps rendering its own header exactly as before.
    expect(screen.getByText("Фактура")).toBeInTheDocument(); // InvoiceCard's own section title
    expect(screen.getByText("Издадена")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "PDF" })).toBeInTheDocument();
    expect(container.querySelector(".border-t.border-slate-100")).not.toBeNull();
  });

  it("displays issued_at and tax_event_date without a day shift", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await screen.findByText("Фактура № 0000000001");
    expect(screen.getByText("2026-03-15")).toBeInTheDocument(); // tax_event_date, raw, no shift
    expect(screen.getByText(new Date(issuedDetail.issued_at).toLocaleString("bg-BG"))).toBeInTheDocument();
  });

  it("displays the frozen seller snapshot", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await screen.findByText("Фактура № 0000000001");
    expect(screen.getByText("Сервиз А")).toBeInTheDocument();
    expect(screen.getByText("гр. София, ул. Примерна 1")).toBeInTheDocument();
    expect(screen.getByText("130489869")).toBeInTheDocument();
  });

  it("displays the frozen buyer snapshot", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await screen.findByText("Фактура № 0000000001");
    expect(screen.getByText("Иван Петров")).toBeInTheDocument();
  });

  it("displays a non-VAT company buyer snapshot with address and EIK, no VAT number", async () => {
    const user = userEvent.setup();
    mockIssueSuccess(nonVatCompanyIssuedDetail);
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await screen.findByText("Фактура № 0000000001");
    expect(screen.getByText("Пример ЕООД")).toBeInTheDocument();
    expect(screen.getByText("Адрес: гр. Пловдив")).toBeInTheDocument();
    expect(screen.getByText("ЕИК: 130489869")).toBeInTheDocument();
    expect(screen.queryByText(/ДДС №:/)).not.toBeInTheDocument();
  });

  it("displays a VAT-registered company buyer snapshot including the VAT number", async () => {
    const user = userEvent.setup();
    mockIssueSuccess(vatCompanyIssuedDetail);
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await screen.findByText("Фактура № 0000000001");
    expect(screen.getByText("ДДС ЕООД")).toBeInTheDocument();
    expect(screen.getByText("Адрес: гр. Варна")).toBeInTheDocument();
    expect(screen.getByText("ЕИК: 130489869")).toBeInTheDocument();
    expect(screen.getByText("ДДС №: BG130489869")).toBeInTheDocument();
  });

  it("shows net/vat/gross from the Issue response, not recomputed", async () => {
    const user = userEvent.setup();
    mockIssueSuccess({ net: 149.5, vat: 0, gross: 149.5 });
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await screen.findByText("Фактура № 0000000001");
    expect(screen.getAllByText("149.50 €")).toHaveLength(2); // net row + gross row
    expect(screen.getByText("ДДС: не се начислява")).toBeInTheDocument();
  });

  it("removes every line-editing control once issued", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await screen.findByText("Фактура № 0000000001");
    expect(screen.queryByRole("button", { name: "Премахни ред" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Добави" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Запази" })).not.toBeInTheDocument();
  });

  it("removes the Issue action once issued", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await screen.findByText("Фактура № 0000000001");
    expect(screen.queryByRole("button", { name: "Издай фактура" })).not.toBeInTheDocument();
  });

  // --- PDF action ---------------------------------------------------

  it("shows no PDF action for a draft invoice", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    renderCard();

    await openDraft(user);
    expect(screen.queryByRole("button", { name: "PDF" })).not.toBeInTheDocument();
  });

  it("shows a PDF action once issued", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    expect(await screen.findByRole("button", { name: "PDF" })).toBeInTheDocument();
  });

  it("PDF action opens the correct invoice PDF endpoint", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());
    await user.click(await screen.findByRole("button", { name: "PDF" }));

    expect(openSpy).toHaveBeenCalledWith("/api/v1/invoices/inv-1/invoice.pdf", "_blank");
    openSpy.mockRestore();
  });

  it("invalidates the order timeline query after a successful Issue", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    const { client } = renderCard("2026-02-10T00:00:00Z");
    client.setQueryData(queryKeys.orderTimeline(orderId), []);
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());
    await screen.findByText("Фактура № 0000000001");

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: queryKeys.orderTimeline(orderId) }),
    );
  });

  // --- Errors -----------------------------------------------------------

  it("shows an actionable message with a settings link on seller_incomplete", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, "invoice_error", "errors.invoices.seller_incomplete"),
    );
    renderCard();

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Попълнете фирмените реквизити (адрес и ЕИК) преди издаване на фактура.",
    );
    expect(screen.getByRole("link", { name: "Настройки → Фирма" })).toHaveAttribute(
      "href", "/settings/company",
    );
  });

  it("displays a VAT-registered seller snapshot with VAT number and charged amount", async () => {
    const user = userEvent.setup();
    mockIssueSuccess(vatRegisteredSellerIssuedDetail);
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await screen.findByText("Фактура № 0000000001");
    expect(screen.getByText("ДДС №: BG130489869")).toBeInTheDocument();
    expect(screen.getByText("ДДС 20%")).toBeInTheDocument();
    expect(screen.getByText("30.00 €")).toBeInTheDocument();
    expect(screen.getByText("180.00 €")).toBeInTheDocument();
    expect(screen.queryByText("ДДС: не се начислява")).not.toBeInTheDocument();
  });

  it("shows an actionable, recoverable message when the buyer's VAT status is unknown", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, "invoice_error", "errors.invoices.buyer_vat_status_unknown"),
    );
    renderCard(null, true, "cust-1");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Уточнете дали клиентът е регистриран по ДДС.",
    );
    expect(screen.getByRole("link", { name: "Данни за клиента" })).toHaveAttribute(
      "href", "/customers/cust-1",
    );
  });

  it("shows an actionable, recoverable message when the buyer's company data is incomplete", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, "invoice_error", "errors.invoices.buyer_incomplete"),
    );
    renderCard(null, true, "cust-1");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Попълнете фирмените данни на клиента преди издаване на фактура.",
    );
    expect(screen.getByRole("link", { name: "Данни за клиента" })).toHaveAttribute(
      "href", "/customers/cust-1",
    );
  });

  it("shows an actionable, recoverable message for an invalid buyer VAT number", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, "invoice_error", "errors.invoices.buyer_vat_number_invalid"),
    );
    renderCard(null, true, "cust-1");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Въведете валиден ДДС номер за клиента.",
    );
    expect(screen.getByRole("link", { name: "Данни за клиента" })).toHaveAttribute(
      "href", "/customers/cust-1",
    );
  });

  it("omits the customer recovery link when no customerId is available", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, "invoice_error", "errors.invoices.buyer_incomplete"),
    );
    renderCard(); // no customerId

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    await screen.findByRole("alert");
    expect(screen.queryByRole("link", { name: "Данни за клиента" })).not.toBeInTheDocument();
  });

  it("renders a subscription-blocked failure with the standard message", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(402, "subscription_not_active", "errors.subscription.mutations_blocked"),
    );
    renderCard();

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Промени не са позволени — абонаментът на компанията не е активен.",
    );
  });

  it("never exposes a raw error body for an unexpected failure", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    vi.mocked(api.post).mockRejectedValue(new Error("ECONNRESET: raw internal detail"));
    renderCard();

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).not.toContain("ECONNRESET");
  });

  it("keeps the dialog open on failure, preserving the selected date", async () => {
    const user = userEvent.setup();
    mockDraftFlow();
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, "invoice_error", "errors.invoices.seller_incomplete"),
    );
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    const dateInput = screen.getByLabelText("Дата на данъчно събитие") as HTMLInputElement;
    await user.clear(dateInput);
    await user.type(dateInput, "2026-02-25");
    await user.click(dialogConfirmButton());

    await screen.findByRole("alert");
    expect(screen.getByLabelText("Дата на данъчно събитие")).toHaveValue("2026-02-25");
  });

  it("allows retry after a failure", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    vi.mocked(api.post).mockReset();
    vi.mocked(api.post)
      .mockRejectedValueOnce(new ApiError(409, "invoice_error", "errors.invoices.seller_incomplete"))
      .mockImplementationOnce(() => {
        vi.mocked(api.get).mockImplementation((path: string) =>
          Promise.resolve(path.startsWith("/invoices?") ? [issuedListItem] : issuedDetail) as never,
        );
        return Promise.resolve(issuedDetail) as never;
      });
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());
    await screen.findByRole("alert");

    await user.click(dialogConfirmButton());

    expect(await screen.findByText("Фактура № 0000000001")).toBeInTheDocument();
    expect(api.post).toHaveBeenCalledTimes(2);
  });

  // --- Annulment (Wave 6 Issue 30) --------------------------------------

  const annulledDetail = {
    ...issuedDetail,
    status: "annulled",
    annulled_at: "2026-03-20T09:00:00Z",
    annul_reason: "Грешно избран клиент",
  };

  function mockAnnulSuccess(): void {
    let annulled = false;
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path.startsWith("/invoices?")) {
        return Promise.resolve([
          { ...issuedListItem, status: annulled ? "annulled" : "issued" },
        ]) as never;
      }
      return Promise.resolve(annulled ? annulledDetail : issuedDetail) as never;
    });
    vi.mocked(api.post).mockImplementation((path: string) => {
      if (path.endsWith("/annul")) {
        annulled = true;
        return Promise.resolve(annulledDetail) as never;
      }
      return Promise.resolve(issuedDetail) as never;
    });
  }

  it("Owner sees an Анулирай фактура action on an issued invoice", async () => {
    mockIssueSuccess();
    vi.mocked(api.get).mockImplementation((path: string) =>
      Promise.resolve(path.startsWith("/invoices?") ? [issuedListItem] : issuedDetail) as never,
    );
    renderCard(null, true);

    expect(await screen.findByRole("button", { name: "Анулирай фактура" })).toBeInTheDocument();
  });

  it("Worker never sees the Анулирай фактура action", async () => {
    vi.mocked(api.get).mockImplementation((path: string) =>
      Promise.resolve(path.startsWith("/invoices?") ? [issuedListItem] : issuedDetail) as never,
    );
    renderCard(null, false);

    await screen.findByText("Издадена");
    expect(screen.queryByRole("button", { name: "Анулирай фактура" })).not.toBeInTheDocument();
  });

  it("requires a non-blank reason before the confirm button is enabled", async () => {
    const user = userEvent.setup();
    mockAnnulSuccess();
    renderCard(null, true);

    await user.click(await screen.findByRole("button", { name: "Анулирай фактура" }));
    const dialog = await screen.findByRole("dialog");
    const confirmButton = within(dialog).getByRole("button", { name: "Анулирай фактура" });
    expect(confirmButton).toBeDisabled();

    await user.type(within(dialog).getByLabelText("Причина за анулиране"), "   ");
    expect(confirmButton).toBeDisabled();

    await user.clear(within(dialog).getByLabelText("Причина за анулиране"));
    await user.type(within(dialog).getByLabelText("Причина за анулиране"), "Грешно избран клиент");
    expect(confirmButton).not.toBeDisabled();
  });

  it("cancel closes the annul dialog without calling the API", async () => {
    const user = userEvent.setup();
    mockAnnulSuccess();
    renderCard(null, true);

    await user.click(await screen.findByRole("button", { name: "Анулирай фактура" }));
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("button", { name: "Отказ" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("submits the reason and shows the annulled banner with date and reason", async () => {
    const user = userEvent.setup();
    mockAnnulSuccess();
    renderCard(null, true);

    await user.click(await screen.findByRole("button", { name: "Анулирай фактура" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Причина за анулиране"), "Грешно избран клиент");
    await user.click(within(dialog).getByRole("button", { name: "Анулирай фактура" }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      "/invoices/inv-1/annul", { reason: "Грешно избран клиент" },
    ));
    expect(await screen.findByText("Тази фактура е анулирана.")).toBeInTheDocument();
    expect(screen.getByText("Причина: Грешно избран клиент")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Анулирай фактура" })).not.toBeInTheDocument();
  });

  it("shows a PDF action for an already-annulled invoice", async () => {
    vi.mocked(api.get).mockImplementation((path: string) =>
      Promise.resolve(path.startsWith("/invoices?")
        ? [{ ...issuedListItem, status: "annulled" }] : annulledDetail) as never,
    );
    renderCard(null, true);

    expect(await screen.findByRole("button", { name: "PDF" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Анулирай фактура" })).not.toBeInTheDocument();
  });

  it("on already_annulled (concurrent annul elsewhere), surfaces the backend error", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockImplementation((path: string) =>
      Promise.resolve(path.startsWith("/invoices?") ? [issuedListItem] : issuedDetail) as never,
    );
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, "invoice_error", "errors.invoices.already_annulled"),
    );
    renderCard(null, true);

    await user.click(await screen.findByRole("button", { name: "Анулирай фактура" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Причина за анулиране"), "Причина");
    await user.click(within(dialog).getByRole("button", { name: "Анулирай фактура" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Фактурата вече е анулирана.");
  });

  it("on not_draft (concurrent Issue elsewhere), refreshes to the real current state", async () => {
    const user = userEvent.setup();
    let issuedElsewhere = false;
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path.startsWith("/invoices?")) {
        return Promise.resolve(issuedElsewhere ? [issuedListItem] : [draftListItem]) as never;
      }
      return Promise.resolve(issuedElsewhere ? issuedDetail : draftDetail) as never;
    });
    vi.mocked(api.post).mockImplementation(() => {
      issuedElsewhere = true;
      return Promise.reject(new ApiError(409, "invoice_error", "errors.invoices.not_draft"));
    });
    renderCard("2026-02-10T00:00:00Z");

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    expect(await screen.findByText("Фактура № 0000000001")).toBeInTheDocument();
  });
});
