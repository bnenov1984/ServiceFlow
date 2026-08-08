import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/Toast";
import { api } from "../lib/api";
import { OrderHeader } from "./OrderHeader";

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
  vi.mocked(api.post).mockReset();
});

// Renders through real react-router Routes (not a bare component render) so
// the Link's `to="/orders"` is exercised end-to-end - clicking it must
// actually land on whatever is mounted at that route, not just carry the
// right `href` string.
//
// statusCode defaults to "received" - a real transition-matrix key (unlike
// the old "new" fixture, which doesn't exist in the generated matrix and
// silently produced zero transitions, so the previous version of this file
// never actually exercised transition rendering at all).
function renderHeader({
  initialEntries = ["/orders/order-1"],
  initialIndex,
  statusCode = "received",
  isOwner = true,
  archived = false,
}: {
  initialEntries?: string[];
  initialIndex?: number;
  statusCode?: string;
  isOwner?: boolean;
  archived?: boolean;
} = {}) {
  mockUseAuth.mockReturnValue({ me: { is_owner: isOwner } });
  vi.mocked(api.get).mockResolvedValue([]);
  vi.mocked(api.post).mockResolvedValue({ warning: null });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={initialEntries} initialIndex={initialIndex}>
          <Routes>
            <Route
              path="/orders/:id"
              element={
                <OrderHeader orderId="order-1" number="2026-00001" statusCode={statusCode} archived={archived} />
              }
            />
            <Route path="/orders" element={<div>ORDERS_BOARD</div>} />
            <Route path="/customers/:id" element={<div>CUSTOMER_PAGE</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("OrderHeader — back to orders control", () => {
  it("renders a keyboard-accessible link with the Bulgarian label", () => {
    renderHeader();

    const link = screen.getByRole("link", { name: "← Поръчки" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/orders");
    expect(link.tagName).toBe("A");
  });

  it("navigates to the RepairFlow Orders route when activated", async () => {
    const user = userEvent.setup();
    renderHeader();

    await user.click(screen.getByRole("link", { name: "← Поръчки" }));

    expect(await screen.findByText("ORDERS_BOARD")).toBeInTheDocument();
  });

  // Regression guard against a history.back() implementation: seed the
  // history stack with an entry that is NOT /orders immediately before the
  // order detail page (as if the order was opened from search or another
  // screen, then that screen was replaced) and land on the order page
  // directly. history.back() would return to that prior entry; explicit
  // navigation to "/orders" always lands on the Orders board regardless of
  // what came before it in history.
  it("lands on /orders regardless of what preceded it in history (not history.back)", async () => {
    const user = userEvent.setup();
    renderHeader({ initialEntries: ["/customers/c1", "/orders/order-1"], initialIndex: 1 });

    await user.click(screen.getByRole("link", { name: "← Поръчки" }));

    expect(await screen.findByText("ORDERS_BOARD")).toBeInTheDocument();
    expect(screen.queryByText("CUSTOMER_PAGE")).not.toBeInTheDocument();
  });

  it("still renders the order number and existing header actions", () => {
    renderHeader();

    expect(screen.getByRole("heading", { name: "№ 2026-00001" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Печат протокол" })).toBeInTheDocument();
  });

  it("existing header actions still work (print protocol opens the right URL)", async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    renderHeader();

    await user.click(screen.getByRole("button", { name: "Печат протокол" }));

    expect(openSpy).toHaveBeenCalledWith("/api/v1/orders/order-1/protocol.pdf?type=intake", "_blank");
    openSpy.mockRestore();
  });
});

describe("OrderHeader — status transition menu", () => {
  it("collapses every allowed transition behind a single trigger instead of one button per transition", () => {
    renderHeader({ statusCode: "received" });

    // "received" alone allows 9 transitions (1 ok next-step, 5 warn
    // skip-ahead, 3 terminal-failure) - previously each rendered as its own
    // always-visible button next to the status pill.
    expect(screen.getByRole("button", { name: /Промени статус/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Диагностика" })).not.toBeInTheDocument();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("opens the menu on click and lists the allowed transitions, closed by default", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "received" });

    const trigger = screen.getByRole("button", { name: /Промени статус/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    const menu = screen.getByRole("menu");
    expect(menu).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Диагностика" })).toBeInTheDocument();
    // "waiting_customer" is a "warn" (skip-ahead) transition: its accessible
    // name carries the skip hint via aria-label, so match on a substring.
    expect(screen.getByRole("menuitem", { name: /Чака клиент/ })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Отказана" })).toBeInTheDocument();
  });

  it("hides the transition-skip terminal-failure options from non-owners", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "received", isOwner: false });

    await user.click(screen.getByRole("button", { name: /Промени статус/ }));

    // OrderHeader's own filter (unchanged by this refactor) drops "cancelled"
    // for non-owners; "declined"/"unrepairable" stay available to everyone.
    expect(screen.queryByRole("menuitem", { name: "Анулирана" })).not.toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Отказана" })).toBeInTheDocument();
  });

  it("selecting a plain 'ok' transition submits the status change and closes the menu", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "received" });

    await user.click(screen.getByRole("button", { name: /Промени статус/ }));
    await user.click(screen.getByRole("menuitem", { name: "Диагностика" }));

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(api.post).toHaveBeenCalledWith("/orders/order-1/status", { to: "diagnostics" });
  });

  it("selecting a terminal-failure transition opens the reason dialog instead of submitting directly", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "received" });

    await user.click(screen.getByRole("button", { name: /Промени статус/ }));
    await user.click(screen.getByRole("menuitem", { name: "Анулирана" }));

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(await screen.findByText("Причина за промяната")).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalledWith("/orders/order-1/status", expect.anything());
  });

  it("does not render the trigger once the order is in a terminal state", () => {
    renderHeader({ statusCode: "delivered" });

    expect(screen.queryByRole("button", { name: /Промени статус/ })).not.toBeInTheDocument();
  });

  it("does not render the trigger for an archived order", () => {
    renderHeader({ statusCode: "received", archived: true });

    expect(screen.queryByRole("button", { name: /Промени статус/ })).not.toBeInTheDocument();
  });
});
