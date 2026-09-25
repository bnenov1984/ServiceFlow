import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/Toast";
import { ApiError, api } from "../lib/api";
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
  warrantyDays = null,
  hasCompletionSnapshot = false,
}: {
  initialEntries?: string[];
  initialIndex?: number;
  statusCode?: string;
  isOwner?: boolean;
  archived?: boolean;
  warrantyDays?: number | null;
  hasCompletionSnapshot?: boolean;
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
                <OrderHeader
                  orderId="order-1" number="2026-00001" statusCode={statusCode}
                  archived={archived} warrantyDays={warrantyDays}
                  hasCompletionSnapshot={hasCompletionSnapshot}
                />
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
    expect(screen.getByRole("button", { name: "Печат протокол (приемане)" })).toBeInTheDocument();
  });

  it("existing header actions still work (print protocol opens the right URL)", async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    renderHeader();

    await user.click(screen.getByRole("button", { name: "Печат протокол (приемане)" }));

    expect(openSpy).toHaveBeenCalledWith("/api/v1/orders/order-1/protocol.pdf?type=intake", "_blank");
    openSpy.mockRestore();
  });
});

describe("OrderHeader — status transition menu", () => {
  it("collapses every allowed transition behind a single trigger instead of one button per transition", () => {
    renderHeader({ statusCode: "received" });

    // "received" alone allows 8 transitions (1 ok next-step, 4 warn
    // skip-ahead, 3 terminal-failure — Wave 2 Issue 5 removed "testing" from
    // the warn skip-ahead set) - previously each rendered as its own
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
    renderHeader({ statusCode: "completed" });

    expect(screen.queryByRole("button", { name: /Промени статус/ })).not.toBeInTheDocument();
  });

  it("does not render the trigger for an archived order", () => {
    renderHeader({ statusCode: "received", archived: true });

    expect(screen.queryByRole("button", { name: /Промени статус/ })).not.toBeInTheDocument();
  });
});

describe("OrderHeader — Wave 4 Issue 7 (delivery protocol action)", () => {
  it("does not render the delivery-protocol button before the order is delivered", () => {
    renderHeader({ statusCode: "ready" });

    expect(screen.queryByRole("button", { name: "Протокол за предаване" })).not.toBeInTheDocument();
  });

  it("opens the delivery protocol PDF when a snapshot exists", async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    renderHeader({ statusCode: "completed", hasCompletionSnapshot: true });

    await user.click(screen.getByRole("button", { name: "Протокол за предаване" }));

    expect(openSpy).toHaveBeenCalledWith(
      "/api/v1/orders/order-1/protocol.pdf?type=delivery", "_blank",
    );
    openSpy.mockRestore();
  });

  it("shows the unavailable message instead of opening a tab when no snapshot exists", async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    renderHeader({ statusCode: "completed", hasCompletionSnapshot: false });

    await user.click(screen.getByRole("button", { name: "Протокол за предаване" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Протокол за предаване не е наличен за тази поръчка.",
    );
    expect(openSpy).not.toHaveBeenCalled();
    openSpy.mockRestore();
  });

  it("still shows the intake protocol action, now distinctly labeled", () => {
    renderHeader({ statusCode: "completed", hasCompletionSnapshot: true });

    expect(screen.getByRole("button", { name: "Печат протокол (приемане)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Протокол за предаване" })).toBeInTheDocument();
  });
});

describe("OrderHeader — protocol email actions (issue 03, audit correction)", () => {
  it("does not render the email actions before the order is completed", () => {
    renderHeader({ statusCode: "ready" });

    expect(screen.queryByRole("button", { name: "Изпрати протокол по имейл" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Изпрати протокол и гаранция по имейл" }),
    ).not.toBeInTheDocument();
  });

  it("sends the plain protocol email with include_warranty: false", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "completed", hasCompletionSnapshot: true });

    await user.click(screen.getByRole("button", { name: "Изпрати протокол по имейл" }));

    expect(api.post).toHaveBeenCalledWith(
      "/orders/order-1/protocol/email", { include_warranty: false },
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Протоколът е изпратен по имейл.",
    );
  });

  it("sends the protocol+warranty email with include_warranty: true", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "completed", hasCompletionSnapshot: true });

    await user.click(screen.getByRole("button", { name: "Изпрати протокол и гаранция по имейл" }));

    expect(api.post).toHaveBeenCalledWith(
      "/orders/order-1/protocol/email", { include_warranty: true },
    );
  });

  it("shows the unavailable message instead of calling the API when no snapshot exists", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "completed", hasCompletionSnapshot: false });

    await user.click(screen.getByRole("button", { name: "Изпрати протокол по имейл" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Протокол за предаване не е наличен за тази поръчка.",
    );
    expect(api.post).not.toHaveBeenCalledWith(
      "/orders/order-1/protocol/email", expect.anything(),
    );
  });

  it("surfaces a backend error by its translated message_key text", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "completed", hasCompletionSnapshot: true });
    vi.mocked(api.post).mockImplementation((url: string) => {
      if (url === "/orders/order-1/protocol/email") {
        return Promise.reject(new ApiError(
          400, "order_error", "errors.protocol.email_missing_customer_email",
        ));
      }
      return Promise.resolve({ warning: null });
    });

    await user.click(screen.getByRole("button", { name: "Изпрати протокол по имейл" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Клиентът няма въведен имейл адрес.",
    );
  });

  it("disables both email buttons while a send is in flight", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "completed", hasCompletionSnapshot: true });
    let resolveSend: (value?: unknown) => void = () => {};
    vi.mocked(api.post).mockImplementation((url: string) => {
      if (url === "/orders/order-1/protocol/email") {
        return new Promise((resolve) => { resolveSend = resolve; }) as never;
      }
      return Promise.resolve({ warning: null });
    });

    await user.click(screen.getByRole("button", { name: "Изпрати протокол по имейл" }));

    expect(screen.getByRole("button", { name: "Зареждане…" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Изпрати протокол и гаранция по имейл" }),
    ).toBeDisabled();

    resolveSend();
  });
});

describe("OrderHeader — dedicated completion button (audit correction, 2026-09-25)", () => {
  it("shows the dedicated 'Приключи поръчката' button only on a ready order", () => {
    renderHeader({ statusCode: "ready" });

    expect(screen.getByRole("button", { name: "Приключи поръчката" })).toBeInTheDocument();
  });

  it("does not show the dedicated button for any other status", () => {
    renderHeader({ statusCode: "received" });

    expect(screen.queryByRole("button", { name: "Приключи поръчката" })).not.toBeInTheDocument();
  });

  it("does not show the dedicated button once archived", () => {
    renderHeader({ statusCode: "ready", archived: true });

    expect(screen.queryByRole("button", { name: "Приключи поръчката" })).not.toBeInTheDocument();
  });

  it("never offers 'Приключена' as a generic status-dropdown option, even on a ready order", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "ready" });

    await user.click(screen.getByRole("button", { name: /Промени статус/ }));

    expect(screen.queryByRole("menuitem", { name: "Приключена" })).not.toBeInTheDocument();
  });

  it("opens the completion dialog when the dedicated button is clicked", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "ready" });

    await user.click(screen.getByRole("button", { name: "Приключи поръчката" }));

    expect(await screen.findByText("Приключване на поръчката")).toBeInTheDocument();
  });

  it("submits the completion transition with to: 'completed' on confirm", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "ready" });

    await user.click(screen.getByRole("button", { name: "Приключи поръчката" }));
    await screen.findByText("Приключване на поръчката");
    await user.click(screen.getByRole("button", { name: "Приключи" }));

    expect(api.post).toHaveBeenCalledWith(
      "/orders/order-1/status", { to: "completed", warranty_days: null },
    );
  });
});
