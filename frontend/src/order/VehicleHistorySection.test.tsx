import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { VehicleHistorySection } from "./VehicleHistorySection";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { ...actual.api, get: vi.fn() } };
});

beforeEach(() => {
  vi.mocked(api.get).mockReset();
});

function renderSection(assetId = "asset-1", currentOrderId = "order-current") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <VehicleHistorySection assetId={assetId} currentOrderId={currentOrderId} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("VehicleHistorySection (Wave 3 Issues 21/26/27)", () => {
  it("shows the empty state when there are no other visits", async () => {
    vi.mocked(api.get).mockResolvedValue({
      asset_id: "asset-1", asset_label: "Golf", current_mileage: null,
      visits: [{
        order_id: "order-current", order_number: "2026-00001", created_at: "2026-08-01T00:00:00Z",
        status_code: "received", customer_id: "c1", customer_name: "Иван",
        complaint: "x", mileage: null,
      }],
    });
    renderSection();

    expect(await screen.findByText("Няма друга история за този автомобил.")).toBeInTheDocument();
  });

  it("excludes the current order and lists other visits with mileage and customer", async () => {
    vi.mocked(api.get).mockResolvedValue({
      asset_id: "asset-1", asset_label: "Golf", current_mileage: 105000,
      visits: [
        {
          order_id: "order-current", order_number: "2026-00002", created_at: "2026-08-15T00:00:00Z",
          status_code: "received", customer_id: "c2", customer_name: "Петър",
          complaint: "Спирачки", mileage: 105000,
        },
        {
          order_id: "order-old", order_number: "2026-00001", created_at: "2026-01-01T00:00:00Z",
          status_code: "delivered", customer_id: "c1", customer_name: "Иван",
          complaint: "Смяна на масло", mileage: 100000,
        },
      ],
    });
    renderSection();

    expect(await screen.findByText("2026-00001")).toBeInTheDocument();
    expect(screen.queryByText("2026-00002")).not.toBeInTheDocument();
    expect(screen.getByText(/Иван/)).toBeInTheDocument();
    expect(screen.getByText(/100000 км/)).toBeInTheDocument();
    expect(screen.getByText("Смяна на масло")).toBeInTheDocument();
  });

  it("omits the mileage fragment for a visit with no recorded mileage", async () => {
    vi.mocked(api.get).mockResolvedValue({
      asset_id: "asset-1", asset_label: "Golf", current_mileage: null,
      visits: [
        {
          order_id: "order-current", order_number: "2026-00002", created_at: "2026-08-15T00:00:00Z",
          status_code: "received", customer_id: "c1", customer_name: "Иван",
          complaint: "x", mileage: null,
        },
        {
          order_id: "order-old", order_number: "2026-00001", created_at: "2026-01-01T00:00:00Z",
          status_code: "delivered", customer_id: "c1", customer_name: "Иван",
          complaint: "Оглед", mileage: null,
        },
      ],
    });
    renderSection();

    const row = await screen.findByText("Оглед");
    expect(row.previousElementSibling?.textContent).toBe("Иван · Предадена");
  });
});
