import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { AccessoriesListSection } from "./AccessoriesListSection";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

beforeEach(() => {
  vi.mocked(api.get).mockReset();
});

interface Item {
  id: string;
  name: string;
  qty: number;
  returned: boolean;
}

function renderSection(items: Item[], accessoriesEnabled: boolean) {
  vi.mocked(api.get).mockResolvedValue(items);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AccessoriesListSection orderId="order-1" accessoriesEnabled={accessoriesEnabled} />
    </QueryClientProvider>,
  );
}

describe("AccessoriesListSection — WP-H accessories-flag gating (Q16/Q16b)", () => {
  it("renders nothing for an automotive order with no accessory history", async () => {
    const { container } = renderSection([], false);

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("still shows a historic accessory on an automotive order, without an add form", async () => {
    renderSection([{ id: "a1", name: "Зарядно", qty: 1, returned: false }], false);

    await screen.findByText("Зарядно");
    expect(screen.queryByPlaceholderText("Друг аксесоар…")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Добави" })).not.toBeInTheDocument();
  });

  it("shows the empty card with an add form for a non-automotive order", async () => {
    renderSection([], true);

    await screen.findByText("Няма аксесоари.");
    expect(screen.getByRole("button", { name: "Добави" })).toBeInTheDocument();
  });
});
