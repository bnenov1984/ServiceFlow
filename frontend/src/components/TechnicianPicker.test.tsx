import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TechnicianPicker, technicianOptions } from "./TechnicianPicker";

const mockGet = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, get: (...args: unknown[]) => mockGet(...args) } };
});

const users = [
  { id: "ivo", name: "Иво Петров", is_active: true },
  { id: "maria", name: "Мария Иванова", is_active: true },
  { id: "georgi", name: "Георги Колев", is_active: true },
  { id: "ana", name: "Ана Стоянова", is_active: true },
  { id: "gone", name: "Напуснал", is_active: false },
];

describe("technicianOptions", () => {
  it("sorts free users first, then by count, and labels each with its load", () => {
    const load = [
      { technician_id: "ivo", active_count: 3 },
      { technician_id: "georgi", active_count: 1 },
    ];
    expect(technicianOptions(users, load)).toEqual([
      { id: "ana", label: "Ана Стоянова · свободен" },
      { id: "maria", label: "Мария Иванова · свободен" },
      { id: "georgi", label: "Георги Колев · 1 активна" },
      { id: "ivo", label: "Иво Петров · 3 активни" },
    ]);
  });

  it("lists plain names sorted by name when the load is unavailable", () => {
    expect(technicianOptions(users, undefined).map((o) => o.label)).toEqual([
      "Ана Стоянова", "Георги Колев", "Иво Петров", "Мария Иванова",
    ]);
  });
});

describe("TechnicianPicker", () => {
  it("still lists names and selects when the load request fails", async () => {
    mockGet.mockImplementation((path: string) =>
      path === "/users" ? Promise.resolve(users) : Promise.reject(new Error("load down")));
    const onChange = vi.fn();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <TechnicianPicker value={null} onChange={onChange} />
      </QueryClientProvider>,
    );

    await userEvent.selectOptions(screen.getByRole("combobox"), await screen.findByRole("option", { name: "Иво Петров" }));
    expect(onChange).toHaveBeenCalledWith("ivo");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Без назначен", "Ана Стоянова", "Георги Колев", "Иво Петров", "Мария Иванова",
    ]);
  });
});
