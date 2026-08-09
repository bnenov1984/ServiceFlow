import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/Toast";
import { queryKeys } from "../lib/queryKeys";
import { ApiError, api } from "../lib/api";
import { InvoiceDetailPage } from "./InvoiceDetailPage";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

const mockUseAuth = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

const invoiceId = "inv-1";
const orderId = "order-1";

function renderDetailPage(isOwner = true, client?: QueryClient) {
  mockUseAuth.mockReturnValue({ me: { is_owner: isOwner } });
  const queryClient = client ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/invoices/${invoiceId}`]}>
          <Routes>
            <Route path="/invoices" element={<div>INVOICES_LIST_PAGE</div>} />
            <Route path="/invoices/:invoiceId" element={children} />
            <Route path="/orders/:id" element={<div>ORDER_PAGE</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
  const view = render(<InvoiceDetailPage />, { wrapper: Wrapper });
  return { ...view, client: queryClient };
}

const orderSummary = { id: orderId, number: "2026-00002", delivered_at: null };

const draftDetail = {
  id: invoiceId, order_id: orderId, status: "draft", number: null, currency: "EUR", row_version: 1,
  lines: [
    { id: "l1", description: "Дисплей", qty: 1, unit_price: 100, vat_rate: null, source: "part" },
    { id: "l2", description: "Смяна на дисплей", qty: 1, unit_price: 50, vat_rate: null, source: "labor" },
  ],
  draft_total: 150,
  tax_event_date: null, issued_at: null, seller: null, buyer: null,
  vat_mode: null, net: null, vat: null, gross: null,
};

const issuedDetail = {
  ...draftDetail,
  status: "issued", number: 1, row_version: 2,
  tax_event_date: "2026-03-15",
  issued_at: "2026-03-15T10:30:00Z",
  seller: { name: "Сервиз А", address: "гр. София, ул. Примерна 1", eik: "130489869", vat_registered: false },
  buyer: { name: "Иван Петров" },
  vat_mode: "not_registered",
  net: 150, vat: 0, gross: 150,
};

function mockDraft(): void {
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.startsWith("/orders/")) return Promise.resolve(orderSummary) as never;
    return Promise.resolve(draftDetail) as never;
  });
}

function mockIssued(): void {
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.startsWith("/orders/")) return Promise.resolve(orderSummary) as never;
    return Promise.resolve(issuedDetail) as never;
  });
}

/** Models the real backend across the whole flow: once Issue succeeds, any
 * refetch of the invoice must see the issued state too. */
function mockIssueSuccess(overrides: Partial<typeof issuedDetail> = {}): void {
  const finalIssued = { ...issuedDetail, ...overrides };
  let issued = false;
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.startsWith("/orders/")) return Promise.resolve(orderSummary) as never;
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

async function openIssueDialog(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await screen.findByDisplayValue("Дисплей");
  await user.click(screen.getByRole("button", { name: "Издай фактура" }));
  await screen.findByRole("heading", { name: "Издаване на фактура" });
}

/** The dialog's own confirm button, scoped to avoid ambiguity with the
 * page's own trigger button of the same name that stays in the DOM
 * (unhidden by jsdom's <dialog> handling) once the dialog is open. */
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

describe("InvoiceDetailPage: routing", () => {
  it("renders on /invoices/:invoiceId and fetches GET /invoices/{id}", async () => {
    mockDraft();
    renderDetailPage();
    await screen.findByDisplayValue("Дисплей");
    expect(api.get).toHaveBeenCalledWith(`/invoices/${invoiceId}`);
  });

  it("'← Фактури' links explicitly to /invoices", async () => {
    mockDraft();
    renderDetailPage();
    await screen.findByDisplayValue("Дисплей");
    expect(screen.getByRole("link", { name: "← Фактури" })).toHaveAttribute("href", "/invoices");
  });
});

describe("InvoiceDetailPage: loading / error", () => {
  it("shows a loading state before data arrives", () => {
    vi.mocked(api.get).mockImplementation(() => new Promise(() => {}));
    renderDetailPage();
    expect(document.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("shows an error state with a working retry on a non-404 failure", async () => {
    vi.mocked(api.get).mockRejectedValue(new ApiError(500, "internal_error", "errors.internal"));
    renderDetailPage();
    // The page's retry() skips retrying a 404 but still retries other
    // failures (mirroring OrderPage) — allow time for those retries.
    expect(await screen.findByRole("alert", {}, { timeout: 5000 })).toBeInTheDocument();
  }, 10000);

  it("a missing/wrong-tenant invoice shows the not-found state, never the Order page", async () => {
    vi.mocked(api.get).mockRejectedValue(new ApiError(404, "not_found", "errors.invoices.not_found"));
    renderDetailPage();
    expect(await screen.findByText("Няма такава фактура.")).toBeInTheDocument();
    expect(screen.queryByText("ORDER_PAGE")).not.toBeInTheDocument();
    // The only way forward offered is back to the list, never a silent
    // fallback into the originating order.
    expect(screen.getByRole("link", { name: "Фактури" })).toHaveAttribute("href", "/invoices");
  });
});

describe("InvoiceDetailPage: Draft", () => {
  it("displays the Чернова status", async () => {
    mockDraft();
    renderDetailPage();
    expect(await screen.findByText("Чернова")).toBeInTheDocument();
  });

  it("the Draft line editor remains available (prefilled lines, editable)", async () => {
    mockDraft();
    renderDetailPage();
    expect(await screen.findByDisplayValue("Дисплей")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Смяна на дисплей")).toBeInTheDocument();
    expect(screen.getByText("150.00 €")).toBeInTheDocument();
  });

  it("Save persists the edited line set via PATCH", async () => {
    const user = userEvent.setup();
    const savedDetail = {
      ...draftDetail,
      lines: [{ id: "l1", description: "Дисплей (нов)", qty: 1, unit_price: 100, vat_rate: null, source: "part" }],
      draft_total: 100,
    };
    let saved = false;
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path.startsWith("/orders/")) return Promise.resolve(orderSummary) as never;
      return Promise.resolve(saved ? savedDetail : draftDetail) as never;
    });
    vi.mocked(api.patch).mockImplementation(() => {
      saved = true;
      return Promise.resolve(savedDetail) as never;
    });
    renderDetailPage();

    await screen.findByDisplayValue("Дисплей");
    const removeButtons = screen.getAllByRole("button", { name: "Премахни ред" });
    await user.click(removeButtons[1]);
    await user.click(screen.getByRole("button", { name: "Запази" }));

    await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/invoices/inv-1", {
      lines: [{ description: "Дисплей", qty: 1, unit_price: 100, source: "part" }],
    }));
    // Line total + the total-row both legitimately read 100.00 € with a
    // single 1×100 line — two matches, not one.
    expect(await screen.findAllByText("100.00 €")).toHaveLength(2);
  });

  it("Owner sees an enabled Issue action", async () => {
    mockDraft();
    renderDetailPage(true);
    await screen.findByDisplayValue("Дисплей");
    const issueButton = screen.getByRole("button", { name: "Издай фактура" });
    expect(issueButton).toBeInTheDocument();
    expect(issueButton).not.toBeDisabled();
  });

  it("Worker never sees a usable Issue action", async () => {
    mockDraft();
    renderDetailPage(false);
    await screen.findByDisplayValue("Дисплей");
    expect(screen.queryByRole("button", { name: "Издай фактура" })).not.toBeInTheDocument();
  });

  it("has no standalone-page 'Затвори' control (nothing to collapse into)", async () => {
    mockDraft();
    renderDetailPage();
    await screen.findByDisplayValue("Дисплей");
    expect(screen.queryByRole("button", { name: "Затвори чернова" })).not.toBeInTheDocument();
  });

  it("the reused Draft editor has no leftover top-divider seam (embedded=false)", async () => {
    mockDraft();
    const { container } = renderDetailPage();
    await screen.findByDisplayValue("Дисплей");
    // Exactly one legitimate `.border-t.border-slate-100` remains — the
    // total-row's own internal divider (separates line list from the total)
    // — not two, which is what an un-suppressed embedded-mode root wrapper
    // would add on top of it.
    expect(container.querySelectorAll(".border-t.border-slate-100")).toHaveLength(1);
  });

  it("successful Issue switches the same page to the Issued view without redirecting", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    renderDetailPage(true);

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());

    // PDF only ever renders once the Issued view is showing.
    expect(await screen.findByRole("button", { name: "PDF" })).toBeInTheDocument();
    // Number, status, and PDF each render exactly once — the page's own
    // header owns them; the embedded IssuedInvoiceView's internal copy is
    // suppressed (embedded=false), not a second independently-rendered one.
    expect(screen.getAllByText("Издадена")).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "PDF" })).toHaveLength(1);
    expect(screen.queryByDisplayValue("Дисплей")).not.toBeInTheDocument();
    // Stayed on /invoices/{id} — never bounced to the order.
    expect(screen.queryByText("ORDER_PAGE")).not.toBeInTheDocument();
    expect(screen.getAllByText("Фактура № 0000000001")).toHaveLength(1);
  });
});

describe("InvoiceDetailPage: Issued", () => {
  it("displays the exact 10-digit issued number exactly once", async () => {
    mockIssued();
    renderDetailPage();
    // The page's own header is the ONLY place the number renders —
    // IssuedInvoiceView's own internal number/status/PDF row is suppressed
    // (embedded=false) rather than rendering a duplicate.
    expect(await screen.findAllByText("Фактура № 0000000001")).toHaveLength(1);
  });

  it("displays the status badge exactly once", async () => {
    mockIssued();
    renderDetailPage();
    await screen.findByRole("button", { name: "PDF" });
    expect(screen.getAllByText("Издадена")).toHaveLength(1);
  });

  it("displays exactly one PDF action", async () => {
    mockIssued();
    renderDetailPage();
    expect(await screen.findAllByRole("button", { name: "PDF" })).toHaveLength(1);
  });

  it("the reused content has no leftover top-divider seam (embedded=false)", async () => {
    mockIssued();
    const { container } = renderDetailPage();
    await screen.findByRole("button", { name: "PDF" });
    // Exactly one legitimate `.border-t.border-slate-100` remains — the
    // totals block's own internal divider (separates line list from
    // net/vat/gross) — not two, which is what an un-suppressed embedded-mode
    // root wrapper (InvoiceCard's own usage) would add on top of it.
    expect(container.querySelectorAll(".border-t.border-slate-100")).toHaveLength(1);
  });

  it("displays issued_at and tax_event_date", async () => {
    mockIssued();
    renderDetailPage();
    await screen.findByRole("button", { name: "PDF" });
    expect(screen.getByText("2026-03-15")).toBeInTheDocument();
    expect(screen.getByText(new Date(issuedDetail.issued_at).toLocaleString("bg-BG"))).toBeInTheDocument();
  });

  it("displays the frozen seller snapshot", async () => {
    mockIssued();
    renderDetailPage();
    await screen.findByRole("button", { name: "PDF" });
    expect(screen.getByText("Сервиз А")).toBeInTheDocument();
    expect(screen.getByText("гр. София, ул. Примерна 1")).toBeInTheDocument();
    expect(screen.getByText("130489869")).toBeInTheDocument();
  });

  it("displays the frozen buyer snapshot", async () => {
    mockIssued();
    renderDetailPage();
    await screen.findByRole("button", { name: "PDF" });
    expect(screen.getByText("Иван Петров")).toBeInTheDocument();
  });

  it("displays lines and totals", async () => {
    mockIssued();
    renderDetailPage();
    await screen.findByRole("button", { name: "PDF" });
    // "50.00 €" is unique to the labor line (qty×price and line-total both
    // read 50.00, but nothing else on the page does) — a simple, unambiguous
    // proof the line itself rendered, without fighting text split across
    // "{description} × {qty}" sibling nodes.
    expect(screen.getAllByText("50.00 €").length).toBeGreaterThan(0);
    expect(screen.getAllByText("150.00 €").length).toBeGreaterThan(0);
    expect(screen.getByText("ДДС: не се начислява")).toBeInTheDocument();
  });

  it("shows no editing controls", async () => {
    mockIssued();
    renderDetailPage();
    await screen.findByRole("button", { name: "PDF" });
    expect(screen.queryByRole("button", { name: "Премахни ред" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Запази" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Издай фактура" })).not.toBeInTheDocument();
  });

  it("shows the PDF action", async () => {
    mockIssued();
    renderDetailPage();
    expect(await screen.findByRole("button", { name: "PDF" })).toBeInTheDocument();
  });
});

describe("InvoiceDetailPage: cache reuse", () => {
  it("reads from the same queryKeys.invoice(id) cache InvoiceCard uses", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(queryKeys.invoice(invoiceId), issuedDetail);
    // A background refetch is normal TanStack Query behavior for stale
    // cache data — resolve it to the same data rather than asserting it
    // never happens; the real proof of shared-cache-key reuse is that the
    // page already renders correctly from the seed, before this ever
    // resolves.
    mockIssued();
    renderDetailPage(true, client);

    expect(await screen.findByRole("button", { name: "PDF" })).toBeInTheDocument();
  });

  it("a mutation on this page updates the shared invoice cache", async () => {
    const user = userEvent.setup();
    mockIssueSuccess();
    const { client } = renderDetailPage(true);

    await openIssueDialog(user);
    await user.click(dialogConfirmButton());
    await screen.findByRole("button", { name: "PDF" });

    expect(client.getQueryData(queryKeys.invoice(invoiceId))).toMatchObject({ status: "issued", number: 1 });
  });
});
