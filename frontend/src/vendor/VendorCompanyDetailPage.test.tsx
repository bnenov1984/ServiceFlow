import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { VendorCompanyDetailPage } from "./VendorCompanyDetailPage";

const mockGet = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, get: (...args: unknown[]) => mockGet(...args) } };
});

function renderPage(id = "c1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/vendor/companies/${id}`]}>
        <Routes>
          <Route path="/vendor/companies" element={<div>COMPANIES_LIST_PAGE</div>} />
          <Route path="/vendor/companies/:id" element={<VendorCompanyDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("VendorCompanyDetailPage", () => {
  it("shows loading skeletons while the company is fetching", () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(document.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("shows a not-found state (with a back link) for a 404", async () => {
    mockGet.mockRejectedValue(
      new ApiError(404, "company_not_found", "errors.provisioning.company_not_found"),
    );
    renderPage();
    expect(await screen.findByText("Няма такава компания.")).toBeInTheDocument();
    expect(screen.getByText("← Компании")).toBeInTheDocument();
  });

  it("shows a generic error state with retry for a non-404 failure", async () => {
    mockGet.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    renderPage();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("renders the full field set for a normal detail response", async () => {
    mockGet.mockResolvedValue({
      id: "c1", name: "Сервиз А", business_profile: "generic_repair",
      active_modules: ["professional-services"], subscription_state: "active",
      trial_ends_at: null, seat_limit: null, seat_usage: 3,
      created_at: "2026-07-01T00:00:00Z", subscription_state_changed_at: "2026-07-15T00:00:00Z",
    });
    renderPage();

    expect(await screen.findByText("Сервиз А")).toBeInTheDocument();
    expect(screen.getByText("generic_repair")).toBeInTheDocument();
    expect(screen.getByText("professional-services")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("3/неограничено")).toBeInTheDocument();
  });
});
