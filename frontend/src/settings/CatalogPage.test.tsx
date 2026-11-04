import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { api } from "../lib/api";
import { CatalogPage } from "./CatalogPage";

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

interface CatalogItem {
  id: string;
  kind: "part" | "labor";
  name: string;
  code: string | null;
  unit: "pcs" | "hour";
  sale_price: number;
  unit_cost: number | null;
  archived: boolean;
}

function render_(items: CatalogItem[], isOwner: boolean) {
  mockUseAuth.mockReturnValue({ me: { is_owner: isOwner } });
  vi.mocked(api.get).mockResolvedValue(items);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <CatalogPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("CatalogPage — WP-I (Q12b, ADR-BOS-013)", () => {
  it("denies access to a non-Owner", async () => {
    render_([], false);
    expect(await screen.findByText("Достъпът е само за собственика на компанията.")).toBeInTheDocument();
  });

  it("lists existing items with kind/price/unit", async () => {
    render_([
      { id: "i1", kind: "part", name: "Дисплей", code: "D-1", unit: "pcs",
        sale_price: 100, unit_cost: 60, archived: false },
      { id: "i2", kind: "labor", name: "Труд (час)", code: null, unit: "hour",
        sale_price: 40, unit_cost: null, archived: false },
    ], true);

    expect(await screen.findByText("Дисплей")).toBeInTheDocument();
    expect(screen.getByText("Труд (час)")).toBeInTheDocument();
    expect(screen.getByText(/100.00 €/)).toBeInTheDocument();
  });

  it("adds a new item via the form", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({});
    render_([], true);

    await screen.findByText("Няма артикули в каталога.");
    await user.type(screen.getByLabelText("Име"), "Нов артикул");
    await user.type(screen.getByLabelText("Продажна цена €"), "25");
    await user.click(screen.getByRole("button", { name: "Добави в каталога" }));

    expect(api.post).toHaveBeenCalledWith("/catalog-items", {
      kind: "part", name: "Нов артикул", unit: "pcs", sale_price: 25,
      code: undefined, unit_cost: undefined,
    });
  });

  it("archives an active item", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({});
    render_([
      { id: "i1", kind: "part", name: "Дисплей", code: null, unit: "pcs",
        sale_price: 100, unit_cost: null, archived: false },
    ], true);

    await screen.findByText("Дисплей");
    await user.click(screen.getByRole("button", { name: "Архивирай" }));

    expect(api.post).toHaveBeenCalledWith("/catalog-items/i1/archive");
  });
});
