import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { LaborLinesSection } from "./LaborLinesSection";

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
  mockUseAuth.mockReturnValue({ me: { is_owner: false } });
});

interface Line {
  id: string;
  catalog_item_id: string | null;
  description: string;
  code: string | null;
  unit: "pcs" | "hour";
  qty: number;
  unit_price: number;
}

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

const FIXED_ITEM: CatalogItem = {
  id: "cat-fixed", kind: "labor", name: "Диагностика", code: null, unit: "pcs",
  sale_price: 20, unit_cost: null, archived: false,
};
const HOURLY_ITEM: CatalogItem = {
  id: "cat-hourly", kind: "labor", name: "Труд (час)", code: null, unit: "hour",
  sale_price: 40, unit_cost: null, archived: false,
};

function mockGet(lines: Line[], catalogItems: CatalogItem[] = [FIXED_ITEM, HOURLY_ITEM]) {
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.startsWith("/catalog-items")) return Promise.resolve(catalogItems);
    return Promise.resolve(lines);
  });
}

function renderSection(lines: Line[], addLineBlockedHint: string | null = null) {
  mockGet(lines);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LaborLinesSection orderId="order-1" addLineBlockedHint={addLineBlockedHint} />
    </QueryClientProvider>,
  );
}

describe("LaborLinesSection — WP-I (catalog-only, fractional hourly qty)", () => {
  it("renders existing lines, showing hours only for an hourly unit", async () => {
    renderSection([
      { id: "l1", catalog_item_id: "cat-fixed", description: "Диагностика", code: null,
        unit: "pcs", qty: 1, unit_price: 20 },
      { id: "l2", catalog_item_id: "cat-hourly", description: "Труд (час)", code: null,
        unit: "hour", qty: 1.5, unit_price: 40 },
    ]);

    expect(await screen.findByText("Диагностика · 20.00 €")).toBeInTheDocument();
    expect(screen.getByText("Труд (час) · 1.5 час · 40.00 €")).toBeInTheDocument();
  });

  it("adds a fixed-price line with no free-text field anywhere", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({});
    renderSection([]);

    await screen.findByText("Няма добавен труд.");
    expect(screen.queryByPlaceholderText("Описание на дейността…")).not.toBeInTheDocument();

    await screen.findByRole("option", { name: /Диагностика/ });
    await user.selectOptions(screen.getByRole("combobox"), "cat-fixed");
    await user.click(screen.getByRole("button", { name: "Добави" }));

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/labor-lines", {
      catalog_item_id: "cat-fixed", qty: "1",
    });
  });

  it("adds an hourly line with a fractional quantity", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({});
    renderSection([]);

    await screen.findByRole("option", { name: /Труд \(час\)/ });
    await user.selectOptions(screen.getByRole("combobox"), "cat-hourly");

    const qtyInput = screen.getByLabelText("Количество");
    await user.clear(qtyInput);
    await user.type(qtyInput, "1.5");
    await user.click(screen.getByRole("button", { name: "Добави" }));

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/labor-lines", {
      catalog_item_id: "cat-hourly", qty: "1.5",
    });
  });

  it("shows the blocked hint instead of the picker when the order's status disallows new lines", async () => {
    renderSection([], "заблокирано в тази статус");

    expect(await screen.findByText("заблокирано в тази статус")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
