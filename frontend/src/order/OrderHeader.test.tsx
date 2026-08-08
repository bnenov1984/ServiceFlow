import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
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

// Renders through real react-router Routes (not a bare component render) so
// the Link's `to="/orders"` is exercised end-to-end - clicking it must
// actually land on whatever is mounted at that route, not just carry the
// right `href` string.
function renderHeader(initialEntries: string[] = ["/orders/order-1"], initialIndex?: number) {
  mockUseAuth.mockReturnValue({ me: { is_owner: true } });
  vi.mocked(api.get).mockResolvedValue([]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={initialEntries} initialIndex={initialIndex}>
          <Routes>
            <Route
              path="/orders/:id"
              element={<OrderHeader orderId="order-1" number="2026-00001" statusCode="new" archived={false} />}
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
    renderHeader(["/customers/c1", "/orders/order-1"], 1);

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
