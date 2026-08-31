import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { KanbanBoard } from "./KanbanBoard";
import type { OrderListItem } from "./types";

function renderBoard(orders: OrderListItem[]) {
  return render(
    <MemoryRouter>
      <KanbanBoard orders={orders} technicians={[]} onDrop={vi.fn()} />
    </MemoryRouter>,
  );
}

function order(overrides: Partial<OrderListItem>): OrderListItem {
  return {
    id: "o1", number: "2026-00001", customer_id: "c1", customer_name: "Иван",
    asset_id: "a1", asset_label: "Toyota Corolla", complaint: "Не пали",
    status_code: "diagnostics", status_kind: "working", technician_id: null,
    priority: "normal", promised_on: null, warranty_days: null,
    origin_order_id: null, status_changed_at: null, overdue: false, archived: false,
    ...overrides,
  };
}

describe("KanbanBoard — Issue 4 (Чака клиент merged into Диагностика)", () => {
  it("renders no standalone 'Чака клиент' column", () => {
    renderBoard([order({ id: "o1", status_code: "waiting_customer" })]);
    expect(screen.queryByRole("heading", { name: "Чака клиент" })).not.toBeInTheDocument();
  });

  it("shows a waiting_customer order inside the Диагностика column, badged", () => {
    renderBoard([
      order({ id: "o1", number: "2026-00001", status_code: "diagnostics" }),
      order({ id: "o2", number: "2026-00002", status_code: "waiting_customer" }),
    ]);
    const heading = screen.getByRole("heading", { name: "Диагностика" });
    const column = heading.closest("div")?.parentElement;
    expect(column).not.toBeNull();
    const withinColumn = within(column as HTMLElement);
    expect(withinColumn.getByText("№ 2026-00001")).toBeInTheDocument();
    expect(withinColumn.getByText("№ 2026-00002")).toBeInTheDocument();
    expect(withinColumn.getByText("Чака клиент")).toBeInTheDocument();
  });

  it("does not badge a plain diagnostics order", () => {
    renderBoard([order({ id: "o1", status_code: "diagnostics" })]);
    expect(screen.queryByText("Чака клиент")).not.toBeInTheDocument();
  });
});
