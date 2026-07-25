import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
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

function renderShell(initialPath: string, activeModules: string[]) {
  mockUseAuth.mockReturnValue({
    me: {
      user_id: "u1", name: "Мария", email: "m@m.bg", is_owner: true, language: "bg",
      company_id: "c1", csrf_token: "t", active_modules: activeModules,
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
          <Route path="/*" element={<AppShell />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Business OS shell: branding and per-app navigation (25.07.2026 rebrand)", () => {
  it("shows Business OS as the platform brand, never ServiceFlow", () => {
    renderShell("/", []);
    expect(screen.getByText("Business OS")).toBeInTheDocument();
    expect(screen.queryByText("ServiceFlow")).not.toBeInTheDocument();
  });

  it("hides the app switcher when only RepairFlow is active (nothing to switch to)", () => {
    renderShell("/", []);
    expect(screen.queryByRole("button", { name: /RepairFlow/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /PropertyFlow/ })).not.toBeInTheDocument();
    const desktopNav = screen.getByRole("navigation", { name: "RepairFlow navigation" });
    expect(within(desktopNav).getByText("Поръчки")).toBeInTheDocument();
  });

  it("shows the app switcher once PropertyFlow is active, defaulting to RepairFlow's own menu", () => {
    renderShell("/", ["professional-services"]);
    expect(screen.getByRole("button", { name: /RepairFlow/ })).toBeInTheDocument();
    const desktopNav = screen.getByRole("navigation", { name: "RepairFlow navigation" });
    expect(within(desktopNav).getByText("Поръчки")).toBeInTheDocument();
    expect(within(desktopNav).getByText("Клиенти")).toBeInTheDocument();
  });

  it("shows PropertyFlow's own menu, not RepairFlow's, on a PropertyFlow route", () => {
    renderShell("/ps", ["professional-services"]);
    const desktopNav = screen.getByRole("navigation", { name: "PropertyFlow navigation" });
    expect(within(desktopNav).queryByText("Поръчки")).not.toBeInTheDocument();
    expect(within(desktopNav).queryByText("Клиенти")).not.toBeInTheDocument();
    expect(within(desktopNav).getByText("PropertyFlow")).toBeInTheDocument();
  });

  it("never renders the retired Bulgarian 'Професионални услуги' label", () => {
    renderShell("/ps", ["professional-services"]);
    expect(screen.queryByText("Професионални услуги")).not.toBeInTheDocument();
  });
});
