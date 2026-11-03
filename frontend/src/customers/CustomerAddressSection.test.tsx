import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { CustomerAddressSection } from "./CustomerAddressSection";
import type { CustomerDetail } from "./types";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { ...actual.api, patch: vi.fn() } };
});

beforeEach(() => {
  vi.mocked(api.patch).mockReset();
});

const customer: CustomerDetail = {
  id: "c1", name: "Иван Петров", phone: "0888123456", phone2: null, email: null,
  is_company: false, vat_registered: null, company_requisites: null,
  address: "ул. Тестова 5", delivery_address: null, archived: false, anonymized: false,
};

function renderSection(c: CustomerDetail) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CustomerAddressSection customerId={c.id} customer={c} />
    </QueryClientProvider>,
  );
}

describe("CustomerAddressSection (order-workflow-revamp WP-B, Q20)", () => {
  it("shows the stored address", () => {
    renderSection(customer);
    expect(screen.getByText("ул. Тестова 5")).toBeInTheDocument();
  });

  it("shows a neutral message when no address is on file", () => {
    renderSection({ ...customer, address: null });
    expect(screen.getByText("Няма зададен адрес.")).toBeInTheDocument();
  });

  it("saves an edited address via PATCH", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection(customer);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    const field = screen.getByLabelText("Адрес");
    await user.clear(field);
    await user.type(field, "нов адрес");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/customers/c1", { address: "нов адрес" });
  });

  it("saves null when the address is cleared to blank", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection(customer);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.clear(screen.getByLabelText("Адрес"));
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/customers/c1", { address: null });
  });
});
