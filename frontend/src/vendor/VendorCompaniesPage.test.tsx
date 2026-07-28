import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { VendorCompaniesPage } from "./VendorCompaniesPage";

const mockGet = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, get: (...args: unknown[]) => mockGet(...args) } };
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/vendor/companies"]}>
        <Routes>
          <Route path="/vendor/companies" element={<VendorCompaniesPage />} />
          <Route path="/vendor/companies/:id" element={<div>COMPANY_DETAIL_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("VendorCompaniesPage", () => {
  it("shows loading skeletons while the list is fetching", () => {
    mockGet.mockReturnValue(new Promise(() => {})); // never resolves
    renderPage();
    expect(document.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("shows an error state with retry on failure", async () => {
    mockGet.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    renderPage();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("shows an empty state when there are no companies", async () => {
    mockGet.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("Няма компании.")).toBeInTheDocument();
  });

  it("renders company rows and navigates to the detail page on click", async () => {
    mockGet.mockResolvedValue([
      {
        id: "c1", name: "Сервиз А", business_profile: "generic_repair",
        active_modules: [], subscription_state: "trial", trial_ends_at: null,
        seat_limit: 5, seat_usage: 2, created_at: "2026-07-01T00:00:00Z",
      },
    ]);
    renderPage();
    const user = userEvent.setup();

    expect(await screen.findByText("Сервиз А")).toBeInTheDocument();
    expect(screen.getByText("2/5")).toBeInTheDocument();

    await user.click(screen.getByText("Сервиз А"));
    expect(await screen.findByText("COMPANY_DETAIL_PAGE")).toBeInTheDocument();
  });
});
