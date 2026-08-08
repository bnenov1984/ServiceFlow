import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: { ...actual.api, get: vi.fn().mockResolvedValue({ status: "ok" }) },
  };
});

const mockUseAuth = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

// Mirrors App.tsx's real nesting (AppShell as the layout route, real routes
// as its Outlet children) so navigation - via the app switcher or the
// RepairFlow toolbar's own button - is exercised for real, not simulated.
function renderShell(initialPath: string, activeModules: string[], isOwner = true) {
  mockUseAuth.mockReturnValue({
    me: {
      user_id: "u1", name: "Мария", email: "m@m.bg", is_owner: isOwner, language: "bg",
      company_id: "c1", csrf_token: "t", active_modules: activeModules,
      seat_limit: null, seat_usage: 1,
    },
    isLoading: false,
    refresh: vi.fn(),
    logout: vi.fn(),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<div>REPAIRFLOW_DASHBOARD</div>} />
            <Route path="orders/new" element={<div>NEW_ORDER_PAGE</div>} />
            <Route path="invoices" element={<div>INVOICES_PAGE</div>} />
            <Route path="ps" element={<div>PROPERTYFLOW_PAGE</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const SEARCH_PLACEHOLDER = "Търсене: клиент, апарат, модел, сериен №…";
const NEW_ORDER_LABEL = "+ Нова поръчка";

describe("Business OS shell: branding and per-app navigation (25.07.2026 rebrand)", () => {
  it("shows Business OS as the platform brand, never ServiceFlow", () => {
    renderShell("/", ["repairflow"]);
    expect(screen.getByText("Business OS")).toBeInTheDocument();
    expect(screen.queryByText("ServiceFlow")).not.toBeInTheDocument();
  });

  it("hides the app switcher when only RepairFlow is active (nothing to switch to)", () => {
    renderShell("/", ["repairflow"]);
    expect(screen.queryByRole("button", { name: /RepairFlow/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /PropertyFlow/ })).not.toBeInTheDocument();
    const desktopNav = screen.getByRole("navigation", { name: "RepairFlow navigation" });
    expect(within(desktopNav).getByText("Поръчки")).toBeInTheDocument();
  });

  it("shows the app switcher once PropertyFlow is active, defaulting to RepairFlow's own menu", () => {
    renderShell("/", ["repairflow", "professional-services"]);
    expect(screen.getByRole("button", { name: /RepairFlow/ })).toBeInTheDocument();
    const desktopNav = screen.getByRole("navigation", { name: "RepairFlow navigation" });
    expect(within(desktopNav).getByText("Поръчки")).toBeInTheDocument();
    expect(within(desktopNav).getByText("Клиенти")).toBeInTheDocument();
  });

  it("shows PropertyFlow's own menu, not RepairFlow's, on a PropertyFlow route", () => {
    renderShell("/ps", ["repairflow", "professional-services"]);
    const desktopNav = screen.getByRole("navigation", { name: "PropertyFlow navigation" });
    expect(within(desktopNav).queryByText("Поръчки")).not.toBeInTheDocument();
    expect(within(desktopNav).queryByText("Клиенти")).not.toBeInTheDocument();
    expect(within(desktopNav).getByText("PropertyFlow")).toBeInTheDocument();
  });

  it("never renders the retired Bulgarian 'Професионални услуги' label", () => {
    renderShell("/ps", ["repairflow", "professional-services"]);
    expect(screen.queryByText("Професионални услуги")).not.toBeInTheDocument();
  });

  it("shows only PropertyFlow's nav and switcher entry for a company with no RepairFlow entitlement", () => {
    renderShell("/ps", ["professional-services"]);
    expect(screen.queryByRole("button", { name: /RepairFlow/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "RepairFlow navigation" })).not.toBeInTheDocument();
    const desktopNav = screen.getByRole("navigation", { name: "PropertyFlow navigation" });
    expect(within(desktopNav).getByText("PropertyFlow")).toBeInTheDocument();
  });

  it("falls back to PropertyFlow as the current app on \"/\" when RepairFlow isn't entitled", () => {
    renderShell("/", ["professional-services"]);
    const desktopNav = screen.getByRole("navigation", { name: "PropertyFlow navigation" });
    expect(within(desktopNav).getByText("PropertyFlow")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(SEARCH_PLACEHOLDER)).not.toBeInTheDocument();
  });
});

describe("Business OS shell: global header vs RepairFlow toolbar (26.07.2026)", () => {
  it("1+2: the global header contains neither the RepairFlow search nor \"Нова поръчка\"", () => {
    renderShell("/", ["repairflow"]);
    const header = screen.getByRole("banner");
    expect(within(header).queryByPlaceholderText(SEARCH_PLACEHOLDER)).not.toBeInTheDocument();
    expect(within(header).queryByText(NEW_ORDER_LABEL)).not.toBeInTheDocument();
  });

  it("3: the RepairFlow route shows the RepairFlow search and \"Нова поръчка\"", () => {
    renderShell("/", ["repairflow"]);
    expect(screen.getByPlaceholderText(SEARCH_PLACEHOLDER)).toBeInTheDocument();
    expect(screen.getByText(NEW_ORDER_LABEL)).toBeInTheDocument();
  });

  it("4: the PropertyFlow route shows neither the RepairFlow search, \"Нова поръчка\", nor any worker/technician context", () => {
    renderShell("/ps", ["repairflow", "professional-services"]);
    expect(screen.queryByPlaceholderText(SEARCH_PLACEHOLDER)).not.toBeInTheDocument();
    expect(screen.queryByText(NEW_ORDER_LABEL)).not.toBeInTheDocument();
    // No such concept exists in the shell at all (verified by audit) - the
    // negative assertion documents that fact rather than asserting nothing.
    expect(screen.queryByText(/technician|worker/i)).not.toBeInTheDocument();
  });

  it("5+6: switching RepairFlow -> PropertyFlow -> RepairFlow removes then restores the toolbar", async () => {
    const user = userEvent.setup();
    renderShell("/", ["repairflow", "professional-services"]);
    expect(screen.getByPlaceholderText(SEARCH_PLACEHOLDER)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /RepairFlow/ }));
    await user.click(screen.getByRole("option", { name: "PropertyFlow" }));
    expect(await screen.findByText("PROPERTYFLOW_PAGE")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(SEARCH_PLACEHOLDER)).not.toBeInTheDocument();
    expect(screen.queryByText(NEW_ORDER_LABEL)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /PropertyFlow/ }));
    await user.click(screen.getByRole("option", { name: "RepairFlow" }));
    expect(await screen.findByText("REPAIRFLOW_DASHBOARD")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(SEARCH_PLACEHOLDER)).toBeInTheDocument();
    expect(screen.getByText(NEW_ORDER_LABEL)).toBeInTheDocument();
  });

  it("7: a direct load of the PropertyFlow route never renders RepairFlow controls (no CSS-only hiding)", () => {
    renderShell("/ps", ["repairflow", "professional-services"]);
    expect(screen.getByText("PROPERTYFLOW_PAGE")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(SEARCH_PLACEHOLDER)).not.toBeInTheDocument();
    expect(screen.queryByText(NEW_ORDER_LABEL)).not.toBeInTheDocument();
  });

  it("8: the account menu stays available globally regardless of the current app", () => {
    renderShell("/ps", ["repairflow", "professional-services"]);
    expect(screen.getByTitle("Профил")).toBeInTheDocument();
    expect(screen.getByText("Мария")).toBeInTheDocument();
  });

  it("9: clicking \"Нова поръчка\" still navigates to the existing create-order route", async () => {
    const user = userEvent.setup();
    renderShell("/", ["repairflow"]);
    await user.click(screen.getByText(NEW_ORDER_LABEL));
    expect(await screen.findByText("NEW_ORDER_PAGE")).toBeInTheDocument();
  });

  it("10: the app switcher and sidebar navigation are unaffected by the toolbar split", () => {
    renderShell("/", ["repairflow", "professional-services"]);
    expect(screen.getByRole("button", { name: /RepairFlow/ })).toBeInTheDocument();
    const desktopNav = screen.getByRole("navigation", { name: "RepairFlow navigation" });
    expect(within(desktopNav).getByText("Табло")).toBeInTheDocument();
    expect(within(desktopNav).getByText("Поръчки")).toBeInTheDocument();
    expect(within(desktopNav).getByText("Клиенти")).toBeInTheDocument();
  });
});

describe("Business OS shell: Настройки nav item (Tenant Employee Management, 29.07.2026)", () => {
  it("is a real link to /settings/employees for an Owner", () => {
    renderShell("/", ["repairflow"], true);
    const desktopNav = screen.getByRole("navigation", { name: "RepairFlow navigation" });
    const link = within(desktopNav).getByRole("link", { name: "Настройки" });
    expect(link).toHaveAttribute("href", "/settings/employees");
  });

  it("stays a grayed, non-clickable placeholder for a Worker", () => {
    renderShell("/", ["repairflow"], false);
    const desktopNav = screen.getByRole("navigation", { name: "RepairFlow navigation" });
    expect(within(desktopNav).queryByRole("link", { name: "Настройки" })).not.toBeInTheDocument();
    expect(within(desktopNav).getByText("Настройки")).toHaveAttribute("aria-disabled");
  });
});

describe("Business OS shell: Фактури nav item (central invoice workspace)", () => {
  it("is a real link to /invoices for an Owner", () => {
    renderShell("/", ["repairflow"], true);
    const desktopNav = screen.getByRole("navigation", { name: "RepairFlow navigation" });
    const link = within(desktopNav).getByRole("link", { name: "Фактури" });
    expect(link).toHaveAttribute("href", "/invoices");
  });

  it("is a real, clickable link for a Worker too — invoice reads are not Owner-only", () => {
    renderShell("/", ["repairflow"], false);
    const desktopNav = screen.getByRole("navigation", { name: "RepairFlow navigation" });
    const link = within(desktopNav).getByRole("link", { name: "Фактури" });
    expect(link).toHaveAttribute("href", "/invoices");
    expect(link).not.toHaveAttribute("aria-disabled");
  });

  it("navigates to the invoices page on click", async () => {
    const user = userEvent.setup();
    renderShell("/", ["repairflow"], true);
    const desktopNav = screen.getByRole("navigation", { name: "RepairFlow navigation" });
    await user.click(within(desktopNav).getByRole("link", { name: "Фактури" }));
    expect(await screen.findByText("INVOICES_PAGE")).toBeInTheDocument();
  });

  it("does not render Фактури at all on a PropertyFlow-only nav", () => {
    renderShell("/ps", ["professional-services"]);
    const desktopNav = screen.getByRole("navigation", { name: "PropertyFlow navigation" });
    expect(within(desktopNav).queryByText("Фактури")).not.toBeInTheDocument();
  });
});
