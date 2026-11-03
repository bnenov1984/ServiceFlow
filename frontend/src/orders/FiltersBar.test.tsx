import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FiltersBar, type OrderFilters } from "./FiltersBar";
import type { UserItem } from "./types";

const EMPTY_FILTERS: OrderFilters = {
  statusCode: "", technicianId: "", priorityHigh: false, overdue: false,
};

const technicians: UserItem[] = [
  { id: "t1", name: "Георги Иванов", is_owner: false, is_active: true },
];

describe("FiltersBar — status chips (order-workflow-revamp WP-K, docs/02 §16)", () => {
  it("shows 'Всички отворени' plus one chip per open status", () => {
    render(<FiltersBar filters={EMPTY_FILTERS} onChange={vi.fn()} technicians={technicians} />);
    expect(screen.getByRole("button", { name: "Всички отворени" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Приета" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Диагностика" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Готова" })).toBeInTheDocument();
  });

  it("clicking a status chip reports that status code, pressed state follows props", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FiltersBar filters={EMPTY_FILTERS} onChange={onChange} technicians={technicians} />);

    await user.click(screen.getByRole("button", { name: "Диагностика" }));
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_FILTERS, statusCode: "diagnostics" });
  });

  it("marks the active status chip as pressed", () => {
    render(
      <FiltersBar
        filters={{ ...EMPTY_FILTERS, statusCode: "diagnostics" }}
        onChange={vi.fn()}
        technicians={technicians}
      />,
    );
    expect(screen.getByRole("button", { name: "Диагностика" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Всички отворени" })).toHaveAttribute("aria-pressed", "false");
  });

  it("no longer offers a Kanban/list view toggle (Q19: Kanban removed)", () => {
    render(<FiltersBar filters={EMPTY_FILTERS} onChange={vi.fn()} technicians={technicians} />);
    expect(screen.queryByRole("button", { name: "Табло" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Списък" })).not.toBeInTheDocument();
  });

  it("keeps the existing technician/priority/overdue filters", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FiltersBar filters={EMPTY_FILTERS} onChange={onChange} technicians={technicians} />);

    expect(screen.getByRole("option", { name: "Георги Иванов" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Само висок приоритет" }));
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_FILTERS, priorityHigh: true });
    await user.click(screen.getByRole("button", { name: "Само просрочени" }));
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_FILTERS, overdue: true });
  });
});
