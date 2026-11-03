import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { OrdersList, sortOrders } from "./OrdersList";
import type { OrderListItem, UserItem } from "./types";

function order(overrides: Partial<OrderListItem>): OrderListItem {
  return {
    id: "o1", number: "2026-00001", customer_id: "c1", customer_name: "Иван Петров",
    asset_id: "a1", asset_label: "Toyota Corolla", complaint: "Не пали",
    status_code: "diagnostics", status_kind: "working", technician_id: null,
    priority: "normal", promised_on: null, warranty_days: null,
    origin_order_id: null, status_changed_at: null, overdue: false, archived: false,
    ...overrides,
  };
}

const technicians: UserItem[] = [
  { id: "t1", name: "Георги Иванов", is_owner: false, is_active: true },
];

function renderList(orders: OrderListItem[], techs: UserItem[] = technicians) {
  return render(
    <MemoryRouter>
      <OrdersList orders={orders} technicians={techs} />
    </MemoryRouter>,
  );
}

describe("sortOrders (order-workflow-revamp WP-K, docs/02 §16: overdue first, then longest in status)", () => {
  it("puts overdue orders before non-overdue ones regardless of status age", () => {
    const fresh = order({ id: "overdue", overdue: true, status_changed_at: new Date().toISOString() });
    const old = order({
      id: "not-overdue", overdue: false,
      status_changed_at: new Date(Date.now() - 10 * 86400_000).toISOString(),
    });
    expect(sortOrders([old, fresh]).map((o) => o.id)).toEqual(["overdue", "not-overdue"]);
  });

  it("within the same overdue-ness, sorts the longest in status first", () => {
    const newer = order({ id: "newer", status_changed_at: new Date(Date.now() - 1 * 86400_000).toISOString() });
    const older = order({ id: "older", status_changed_at: new Date(Date.now() - 5 * 86400_000).toISOString() });
    expect(sortOrders([newer, older]).map((o) => o.id)).toEqual(["older", "newer"]);
  });
});

describe("OrdersList — table (order-workflow-revamp WP-K)", () => {
  it("renders the decided columns with the order's data", () => {
    renderList([
      order({
        id: "o1", number: "2026-00001", customer_name: "Иван Петров", asset_label: "Toyota Corolla",
        status_code: "diagnostics", technician_id: "t1",
        promised_on: "2026-11-10", status_changed_at: new Date(Date.now() - 2 * 86400_000).toISOString(),
      }),
    ]);

    const table = screen.getByRole("table");
    const row = within(table).getByRole("row", { name: /2026-00001/ });
    expect(within(row).getByRole("link", { name: "№ 2026-00001" })).toHaveAttribute("href", "/orders/o1");
    expect(within(row).getByText("Диагностика")).toBeInTheDocument();
    expect(within(row).getByText("Иван Петров")).toBeInTheDocument();
    expect(within(row).getByText("Toyota Corolla")).toBeInTheDocument();
    expect(within(row).getByText("Георги Иванов")).toBeInTheDocument();
    expect(within(row).getByText("2 дни в статус")).toBeInTheDocument();
  });

  it("shows an unassigned-technician label when no technician is set", () => {
    renderList([order({ technician_id: null })]);
    const table = screen.getByRole("table");
    expect(within(table).getByText("Без техник")).toBeInTheDocument();
  });

  it("has no status-change controls — status changes only happen on the order page (Q19b)", () => {
    renderList([order({ status_code: "diagnostics" })]);
    // Every forward transition from "diagnostics" would have been offered as
    // a button under the old OrderStatusActions; none should exist now.
    expect(screen.queryByRole("button", { name: "Ремонт" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Чака части" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders the overdue and priority badges", () => {
    renderList([order({ overdue: true, priority: "high" })]);
    const table = screen.getByRole("table");
    expect(within(table).getByText("Просрочена")).toBeInTheDocument();
    expect(within(table).getByText("Приоритет")).toBeInTheDocument();
  });

  it("sorts overdue orders to the top of the rendered table", () => {
    renderList([
      order({ id: "o1", number: "2026-00001", overdue: false, status_changed_at: new Date().toISOString() }),
      order({ id: "o2", number: "2026-00002", overdue: true, status_changed_at: new Date().toISOString() }),
    ]);
    const table = screen.getByRole("table");
    const rows = within(table).getAllByRole("row").slice(1); // drop the header row
    expect(within(rows[0]).getByText("№ 2026-00002")).toBeInTheDocument();
  });

  it("also renders the same data as a mobile card list (Q19b: stacked cards on phone)", () => {
    renderList([order({ number: "2026-00001", customer_name: "Иван Петров", asset_label: "Toyota Corolla" })]);
    // Both renderings exist in the DOM (CSS breakpoint-toggled) — the card
    // list uses <li>, never a <tr>, so this is unambiguous.
    const cardList = screen.getByRole("list");
    expect(within(cardList).getByRole("link", { name: "№ 2026-00001" })).toBeInTheDocument();
    expect(within(cardList).getByText("Иван Петров · Toyota Corolla")).toBeInTheDocument();
  });
});
