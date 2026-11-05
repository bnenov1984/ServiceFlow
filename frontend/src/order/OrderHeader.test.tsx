import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
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
// statusCode defaults to "diagnostics" — a real transition-matrix key with a
// real forward-dropdown menu. order-workflow-revamp WP-G (Q1/Q2c) gave
// "received" an entirely different, dedicated UI (ПРИЕМИ/ОТКАЖИ, no generic
// dropdown at all) — see the "OrderHeader — НОВА (received)" describe block
// below for that status specifically.
function renderHeader({
  initialEntries = ["/orders/order-1"],
  initialIndex,
  statusCode = "diagnostics",
  isOwner = true,
  archived = false,
  warrantyDays = null,
  hasCompletionSnapshot = false,
  technicianId = null,
  users = [] as { id: string; name: string; is_active: boolean }[],
}: {
  initialEntries?: string[];
  initialIndex?: number;
  statusCode?: string;
  isOwner?: boolean;
  archived?: boolean;
  warrantyDays?: number | null;
  hasCompletionSnapshot?: boolean;
  technicianId?: string | null;
  // order-workflow-revamp WP-G: AcceptDialog's TechnicianPicker mounts
  // (and fires its own GET /users) as soon as OrderHeader itself mounts —
  // it's always rendered, only its dialog's `open` prop toggles — so this
  // must be configured here, before the first render, not inside an
  // individual test after the fact (too late: the query has already fired
  // against whatever mock was active at mount time).
  users?: { id: string; name: string; is_active: boolean }[];
} = {}) {
  mockUseAuth.mockReturnValue({ me: { is_owner: isOwner } });
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path === "/users") return Promise.resolve(users);
    return Promise.resolve([]);
  });
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
                  technicianId={technicianId}
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
    renderHeader({ statusCode: "diagnostics" });

    // order-workflow-revamp WP-G: "diagnostics" forwards to 3 plain-ok
    // statuses (waiting_customer/waiting_parts/repair), 1 warn skip-ahead
    // (ready), and 3 terminal-failure (declined/unrepairable/cancelled) —
    // each rendered behind the one trigger, never its own always-visible
    // button next to the status pill.
    expect(screen.getByRole("button", { name: /Промени статус/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ремонт" })).not.toBeInTheDocument();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("opens the menu on click and lists the allowed transitions, closed by default", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "diagnostics" });

    const trigger = screen.getByRole("button", { name: /Промени статус/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    const menu = screen.getByRole("menu");
    expect(menu).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Ремонт" })).toBeInTheDocument();
    // "ready" is a "warn" (skip-ahead) transition: its accessible name
    // carries the skip hint via aria-label, so match on a substring.
    expect(screen.getByRole("menuitem", { name: /Готова/ })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Отказана" })).toBeInTheDocument();
  });

  it("hides the transition-skip terminal-failure options from non-owners", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "diagnostics", isOwner: false });

    await user.click(screen.getByRole("button", { name: /Промени статус/ }));

    // OrderHeader's own filter (unchanged by this refactor) drops "cancelled"
    // for non-owners; "declined"/"unrepairable" stay available to everyone.
    expect(screen.queryByRole("menuitem", { name: "Анулирана" })).not.toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Отказана" })).toBeInTheDocument();
  });

  it("selecting a plain 'ok' transition submits the status change and closes the menu", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "diagnostics" });

    await user.click(screen.getByRole("button", { name: /Промени статус/ }));
    await user.click(screen.getByRole("menuitem", { name: "Ремонт" }));

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(api.post).toHaveBeenCalledWith("/orders/order-1/status", { to: "repair" });
  });

  it("selecting a terminal-failure transition opens the reason dialog instead of submitting directly", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "diagnostics" });

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
    renderHeader({ statusCode: "diagnostics", archived: true });

    expect(screen.queryByRole("button", { name: /Промени статус/ })).not.toBeInTheDocument();
  });

  it("never shows the generic dropdown trigger for a НОВА (received) order", () => {
    renderHeader({ statusCode: "received" });

    expect(screen.queryByRole("button", { name: /Промени статус/ })).not.toBeInTheDocument();
  });
});

describe("OrderHeader — НОВА (Q1/Q2a/Q2b/Q2c)", () => {
  it("shows dedicated ПРИЕМИ/ОТКАЖИ buttons instead of the generic menu", () => {
    renderHeader({ statusCode: "received" });

    expect(screen.getByRole("button", { name: "Приеми" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Откажи" })).toBeInTheDocument();
  });

  it("shows the cancel-order link to an Owner", () => {
    renderHeader({ statusCode: "received", isOwner: true });
    expect(screen.getByRole("button", { name: "Анулирай поръчката" })).toBeInTheDocument();
  });

  it("hides the cancel-order link from a non-owner", () => {
    renderHeader({ statusCode: "received", isOwner: false });
    expect(screen.queryByRole("button", { name: "Анулирай поръчката" })).not.toBeInTheDocument();
  });

  it("ОТКАЖИ opens the reason dialog targeting 'declined'", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "received" });

    await user.click(screen.getByRole("button", { name: "Откажи" }));
    const dialog = (await screen.findByText("Причина за промяната")).closest("dialog")!;

    await user.type(within(dialog).getByRole("textbox"), "Клиентът се отказа веднага");
    await user.click(within(dialog).getByRole("button", { name: "Потвърди" }));

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/status", {
      to: "declined", reason: "Клиентът се отказа веднага",
    });
  });

  it("ПРИЕМИ opens a technician picker pre-filled from intake and submits both in one request", async () => {
    const user = userEvent.setup();
    renderHeader({
      statusCode: "received", technicianId: "tech-1",
      users: [
        { id: "tech-1", name: "Георги", is_active: true },
        { id: "tech-2", name: "Иван", is_active: true },
      ],
    });

    await user.click(screen.getByRole("button", { name: "Приеми" }));
    await screen.findByText("Приемане на поръчката");
    await screen.findByRole("option", { name: /Георги/ });
    const picker = screen.getByLabelText("Техник") as HTMLSelectElement;
    expect(picker).toHaveValue("tech-1");

    const confirmButtons = screen.getAllByRole("button", { name: "Приеми" });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/status", {
      to: "diagnostics", technician_id: "tech-1",
    });
  });

  it("ПРИЕМИ requires picking a technician when intake didn't set one", async () => {
    const user = userEvent.setup();
    renderHeader({
      statusCode: "received", technicianId: null,
      users: [{ id: "tech-1", name: "Георги", is_active: true }],
    });

    await user.click(screen.getByRole("button", { name: "Приеми" }));
    await screen.findByText("Приемане на поръчката");
    await screen.findByRole("option", { name: /Георги/ });

    const confirmButtons = screen.getAllByRole("button", { name: "Приеми" });
    const dialogConfirm = confirmButtons[confirmButtons.length - 1];
    expect(dialogConfirm).toBeDisabled();

    await user.selectOptions(screen.getByLabelText("Техник"), "tech-1");
    expect(dialogConfirm).not.toBeDisabled();
  });
});

describe("OrderHeader — backward transitions, 'Върни към…' (Q3/Q3b)", () => {
  it("offers a backward action for a status with a BACK target, separate from the forward menu", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "repair" });

    const backButton = screen.getByRole("button", { name: /Върни към Диагностика/ });
    expect(backButton).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Промени статус/ }));
    expect(screen.queryByRole("menuitem", { name: "Диагностика" })).not.toBeInTheDocument();
  });

  it("requires a mandatory reason and submits it with the backward transition", async () => {
    const user = userEvent.setup();
    renderHeader({ statusCode: "repair" });

    await user.click(screen.getByRole("button", { name: /Върни към Диагностика/ }));
    const dialog = (await screen.findByText("Върни към Диагностика", { selector: "h2" }))
      .closest("dialog")!;
    const confirm = within(dialog).getByRole("button", { name: "Потвърди" });
    expect(confirm).toBeDisabled();

    await user.type(within(dialog).getByRole("textbox"), "Оказа се друг проблем");
    expect(confirm).not.toBeDisabled();
    await user.click(confirm);

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/status", {
      to: "diagnostics", reason: "Оказа се друг проблем",
    });
  });

  it("offers no backward action for a status with no BACK target (e.g. diagnostics)", () => {
    renderHeader({ statusCode: "diagnostics" });

    expect(screen.queryByRole("button", { name: /Върни към/ })).not.toBeInTheDocument();
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
